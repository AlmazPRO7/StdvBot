import matplotlib
matplotlib.use('Agg') # Fix for thread safety
import logging
import pandas as pd
import os
import json
import io
import asyncio
import time
import html
import re
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo, MenuButtonWebApp
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, CallbackQueryHandler, filters
from src.config import Config
from src.llm_client import GeminiClient
from src.prompts import ANALYST_SYSTEM_PROMPT, SUPPORT_AGENT_SYSTEM_PROMPT, VISION_SYSTEM_PROMPT, BLAME_SYSTEM_PROMPT, UNIVERSAL_AGENT_SYSTEM_PROMPT, POLICY_AGENT_SYSTEM_PROMPT
from src.visualizer import create_dashboard
from src.rag_engine import RAGSystem

# --- PROMPT ENGINEERING TOOLS ---
from prompt_engineering.prompt_manager import PromptManager
from prompt_engineering.advanced_tools import LLMJudge
from prompt_engineering.visualization import Visualizer as PromptVisualizer

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

ai_client = GeminiClient()  # Использует Config.AI_PROVIDER (auto)
prompt_manager = PromptManager()
judge = LLMJudge()
prompt_visualizer = PromptVisualizer()
rag_system = RAGSystem("data/knowledge_base.txt")

MAIN_KEYBOARD = [
    [KeyboardButton("📂 Пример CSV"), KeyboardButton("📷 Анализ Фото")],
    [KeyboardButton("🎤 Голосовой вопрос"), KeyboardButton("🆘 Справка")]
]

def clean_response(text):
    """
    Очищает ответ. 
    1. Если есть Markdown блок ```...```, вытаскиваем ТОЛЬКО его содержимое.
    2. Санитизируем ссылки SDVOR (удаляем бренды для мелочевки).
    3. Если это 'грязный' HTML (ошибка), экранируем.
    """
    if not text: return ""
    
    # 1. Агрессивное извлечение из Markdown блока
    code_block_match = re.search(r'```(?:html)?\s*(.*?)\s*```', text, re.DOTALL | re.IGNORECASE)
    if code_block_match:
        text = code_block_match.group(1)
    else:
        text = re.sub(r'^```(html)?\s*', '', text, flags=re.IGNORECASE)
        text = re.sub(r'\s*```$', '', text)
    
    text = text.strip()
    
    # 2. Санитизация ссылок (Hard Fix)
    text = sanitize_sdvor_links(text)
    
    # 3. Удаляем совсем мусор (структурные теги)
    text = re.sub(r'<!DOCTYPE[^>]*>', '', text, flags=re.IGNORECASE)
    text = re.sub(r'<\/?(html|head|body)[^>]*>', '', text, flags=re.IGNORECASE)
    text = text.strip()

    # 4. Проверка на запрещенные теги
    forbidden_pattern = re.compile(r'<\/?(title|script|style|div|p|h[1-6]|br|table|tr|td|li|ul)', re.IGNORECASE)
    
    if forbidden_pattern.search(text):
        return html.escape(text)
    
    return text

def sanitize_sdvor_links(text):
    """
    Принудительно чистит ссылки на Стройдвор.
    1. Удаляет регион /ekb/.
    2. Использует правильный параметр freeTextSearch.
    3. Пропускает ПОЛНЫЙ запрос (Бренд + Модель), так как поиск стал умным.
    """
    import urllib.parse
    
    def replacer(match):
        original_url = match.group(0)
        # Группа 1: значение параметра (text или freeTextSearch)
        query_param = match.group(1)
        
        try:
            decoded = urllib.parse.unquote_plus(query_param).strip()
            
            if not decoded: return original_url
            
            # Кодируем весь запрос целиком
            new_query = urllib.parse.quote_plus(decoded)
            
            # Генерируем ссылку БЕЗ региона и с ПРАВИЛЬНЫМ параметром
            return f'href="https://sdvor.com/search?freeTextSearch={new_query}"'
            
        except Exception as e:
            logging.error(f"Link sanitization error: {e}")
            return original_url

    pattern = r'href="https://(?:www\.)?sdvor\.com(?:/ekb)?/search\?(?:text|freeTextSearch)=([^"]+)"'
    return re.sub(pattern, replacer, text)

# --- MIDDLEWARE: SMART AUTO-DELETE ---
# Хранит ID сообщений для удаления при следующем действии
_deletable_messages: dict[int, list[int]] = {}  # chat_id -> [message_ids]
_permanent_messages: dict[int, set[int]] = {}   # chat_id -> {message_ids} - НЕ удалять
_welcome_messages: dict[int, int] = {}  # chat_id -> welcome_message_id (одно на чат)

async def mark_for_delete(context: ContextTypes.DEFAULT_TYPE, chat_id: int, message_id: int):
    """Помечает сообщение для удаления при следующем действии пользователя"""
    if chat_id not in _deletable_messages:
        _deletable_messages[chat_id] = []
    if message_id not in _deletable_messages[chat_id]:
        _deletable_messages[chat_id].append(message_id)

async def mark_permanent(chat_id: int, message_id: int):
    """Помечает сообщение как постоянное (НЕ удалять)"""
    if chat_id not in _permanent_messages:
        _permanent_messages[chat_id] = set()
    _permanent_messages[chat_id].add(message_id)

async def cleanup_previous(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    """Удаляет все помеченные сообщения (вызывать при новом действии)"""
    if chat_id not in _deletable_messages:
        return

    permanent = _permanent_messages.get(chat_id, set())
    to_delete = [mid for mid in _deletable_messages[chat_id] if mid not in permanent]

    for message_id in to_delete:
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
        except Exception as e:
            logging.debug(f"Delete failed (msg {message_id}): {e}")

    # Очищаем список
    _deletable_messages[chat_id] = []

async def schedule_delete(context: ContextTypes.DEFAULT_TYPE, chat_id: int, message_id: int, delay: int = 15):
    """Legacy: Планировщик удаления по таймеру (для совместимости)"""
    async def delete_task():
        await asyncio.sleep(delay)
        permanent = _permanent_messages.get(chat_id, set())
        if message_id in permanent:
            return  # Не удаляем permanent сообщения
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
        except Exception as e:
            logging.debug(f"Delete failed (msg {message_id}): {e}")

    asyncio.create_task(delete_task())

# --- ADMIN PANEL ---
async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user.username
    # В продакшене здесь должна быть проверка user_id или username из Config
    # if f"@{user}" != Config.ADMIN_USER:
    #     await update.message.reply_text("⛔ Доступ запрещен.")
    #     return

    keyboard = [
        [InlineKeyboardButton("📊 Статистика (Plot)", callback_data='admin_stats')],
        [InlineKeyboardButton("⚖️ Оценить последний ответ", callback_data='admin_judge')],
        [InlineKeyboardButton("📝 Промпты", callback_data='admin_prompts')]
    ]
    await update.message.reply_text("🛠 <b>Admin Dashboard:</b>", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    # Проверяем: если приветствие уже есть И не удалено — не дублируем
    if chat_id in _welcome_messages:
        welcome_id = _welcome_messages[chat_id]
        # Проверяем, существует ли сообщение (пробуем закрепить — если удалено, будет ошибка)
        try:
            await context.bot.pin_chat_message(chat_id=chat_id, message_id=welcome_id, disable_notification=True)
            # Сообщение существует — удаляем /start и выходим
            try:
                await context.bot.delete_message(chat_id=chat_id, message_id=update.message.message_id)
            except Exception:
                pass
            return
        except Exception:
            # Сообщение удалено — продолжаем отправку нового
            del _welcome_messages[chat_id]
            if chat_id in _permanent_messages and welcome_id in _permanent_messages[chat_id]:
                _permanent_messages[chat_id].discard(welcome_id)

    # 1. Пытаемся получить динамический Cloudflare URL
    webapp_url = "https://python-telegram-bot.org/static/webappbot/demo.html" # Fallback
    try:
        if os.path.exists("tunnel_url.txt"):
            with open("tunnel_url.txt", "r") as f:
                content = f.read().strip()
                if content.startswith("https://"):
                    webapp_url = content
    except Exception as e:
        logging.error(f"Error reading tunnel URL: {e}")

    # Добавляем timestamp чтобы сбросить кэш кнопки в Telegram
    webapp_url_with_cachebust = f"{webapp_url}?t={int(time.time())}"

    # 2. Настраиваем Синюю кнопку Меню (WebApp)
    try:
        await context.bot.set_chat_menu_button(
            chat_id=chat_id,
            menu_button=MenuButtonWebApp(
                text="Графики",
                web_app=WebAppInfo(url=webapp_url_with_cachebust)
            )
        )
    except Exception as e:
        logging.error(f"Failed to set menu button: {e}")

    # 3. Явно создаем клавиатуру
    kb = [
        [KeyboardButton("📂 Пример CSV"), KeyboardButton("📷 Анализ Фото")],
        [KeyboardButton("🎤 Голосовой вопрос"), KeyboardButton("🆘 Справка")]
    ]
    markup = ReplyKeyboardMarkup(kb, resize_keyboard=True)

    # Формируем улучшенное приветственное сообщение
    welcome_message = (
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "🏗 <b>СТРОИТЕЛЬНЫЙ ДВОР AI</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

        "🤖 <b>Интеллектуальный ассистент</b> для клиентов\n"
        "строительного ритейла на базе <b>Generative AI</b>\n\n"

        "┌─────────────────────────────────────┐\n"
        "│  🧠 <b>ВОЗМОЖНОСТИ СИСТЕМЫ</b>            │\n"
        "├─────────────────────────────────────┤\n"
        "│ ✦ <b>Multi-Agent</b> — умная маршрутизация    │\n"
        "│ ✦ <b>RAG Search</b> — поиск по базе знаний   │\n"
        "│ ✦ <b>Vision AI</b> — анализ фото товаров     │\n"
        "│ ✦ <b>Voice</b> — голосовые сообщения         │\n"
        "└─────────────────────────────────────┘\n\n"

        "📊 <b>МЕТРИКИ И АНАЛИТИКА</b>\n"
        "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        f"🔗 <a href='{webapp_url}'>Открыть Dashboard</a> │ "
        "Кнопка <b>[Графики]</b> в меню\n\n"

        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "👨‍💻 <b>РАЗРАБОТЧИК</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "   <b>Almaz</b> • AI/ML Engineer\n"
        "   🎓 Microsoft Learn Certified\n\n"

        "   🔗 <a href='https://github.com/AlmazPRO7/StdvBot'>GitHub: StdvBot</a>\n"
        "   🎖 <a href='https://learn.microsoft.com/ru-ru/users/54773151/'>Microsoft Learn Profile</a>\n\n"

        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "💬 Напишите ваш вопрос или выберите действие:\n"
    )

    # Удаляем предыдущие временные сообщения
    await cleanup_previous(context, chat_id)

    # Отправляем приветствие
    welcome_msg = await update.message.reply_text(
        welcome_message,
        reply_markup=markup,
        parse_mode="HTML",
        disable_web_page_preview=True
    )

    # Сохраняем ID приветствия (одно на чат)
    _welcome_messages[chat_id] = welcome_msg.message_id

    # Приветствие - PERMANENT (не удаляем)
    await mark_permanent(chat_id, welcome_msg.message_id)

    # Закрепляем приветствие
    try:
        await context.bot.pin_chat_message(chat_id=chat_id, message_id=welcome_msg.message_id, disable_notification=True)
    except Exception as e:
        logging.debug(f"Failed to pin welcome: {e}")

    # Сообщение пользователя (/start) удаляем сразу
    try:
        await context.bot.delete_message(chat_id=chat_id, message_id=update.message.message_id)
    except Exception:
        pass

async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "📚 <b>СПРАВОЧНЫЙ ЦЕНТР</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

        "🤖 <b>Что умеет этот бот?</b>\n"
        "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        "Интеллектуальный помощник для клиентов\n"
        "строительного магазина «Строительный Двор»\n\n"

        "📋 <b>БЫСТРЫЕ КОМАНДЫ</b>\n"
        "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        "• /start — Перезапуск бота\n"
        "• 📂 <b>Пример CSV</b> — Батч-анализ данных\n"
        "• 📷 <b>Анализ Фото</b> — Распознание товаров\n"
        "• 🎤 <b>Голосовой вопрос</b> — Голосовые запросы\n\n"

        "👇 <b>Выберите раздел справки:</b>"
    )

    keyboard = [
        [InlineKeyboardButton("👔 Бизнес-возможности", callback_data='help_manager')],
        [InlineKeyboardButton("🛠 Техническая архитектура", callback_data='help_tech')],
        [InlineKeyboardButton("📊 Метрики и аналитика", callback_data='help_metrics')],
        [InlineKeyboardButton("👨‍💻 О разработчике", callback_data='help_author')]
    ]
    await update.message.reply_text(help_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == 'help_manager':
        text = (
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "👔 <b>БИЗНЕС-ВОЗМОЖНОСТИ</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

            "🎯 <b>УМНАЯ МАРШРУТИЗАЦИЯ</b>\n"
            "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
            "✦ Автоопределение типа обращения\n"
            "   <i>Жалоба • Продажа • Тех.вопрос • Спам</i>\n"
            "✦ Анализ настроения клиента (Sentiment)\n"
            "✦ Оценка срочности и приоритета\n\n"

            "🛡 <b>АВТОПОДДЕРЖКА</b>\n"
            "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
            "✦ Эмпатичные ответы за 2 секунды\n"
            "✦ Brand Safety — защита репутации\n"
            "✦ Готовые действия: <i>Возврат, Эскалация</i>\n\n"

            "🛒 <b>ПРОДАЖИ И ПОИСК</b>\n"
            "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
            "✦ Понимает: <i>«10 листов ГКЛ + профили»</i>\n"
            "✦ Поиск по каталогу Строительный Двор\n"
            "✦ Подбор аналогов и комплектующих\n\n"

            "📱 <b>МУЛЬТИМОДАЛЬНОСТЬ</b>\n"
            "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
            "✦ 🎤 Голос — понимает речь клиента\n"
            "✦ 📷 Фото — распознаёт стройматериалы\n"
            "✦ 📊 CSV — батч-обработка данных\n"
        )
        keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data='help_back')]]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

    elif data == 'help_tech':
        text = (
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "🛠 <b>ТЕХНИЧЕСКАЯ АРХИТЕКТУРА</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

            "🏗 <b>AGENTIC WORKFLOW</b>\n"
            "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
            "✦ <b>Analyst</b> — классификация Intent→JSON\n"
            "✦ <b>Sales Agent</b> — продажи и поиск\n"
            "✦ <b>Support Agent</b> — обработка жалоб\n"
            "✦ <b>Vision Agent</b> — анализ изображений\n\n"

            "🧠 <b>LLM ORCHESTRATION</b>\n"
            "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
            "✦ <b>Primary:</b> Gemini 2.0 Flash (Direct API)\n"
            "✦ <b>Fallback:</b> OpenRouter (Auto-rotation)\n"
            "✦ <b>Features:</b> JSON Mode, Vision, Audio\n\n"

            "⚙️ <b>ENGINEERING STACK</b>\n"
            "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
            "✦ Python 3.12 + python-telegram-bot\n"
            "✦ RAG: BM25 + TF-IDF Hybrid Search\n"
            "✦ Circuit Breaker + Retry Logic\n"
            "✦ A/B Testing + Metrics Dashboard\n\n"

            "📦 <b>ENTERPRISE FEATURES</b>\n"
            "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
            "✦ Docker + Healthcheck + Auto-restart\n"
            "✦ JSON Structured Logging\n"
            "✦ Graceful Degradation\n"
        )
        keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data='help_back')]]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

    elif data == 'help_metrics':
        text = (
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "📊 <b>МЕТРИКИ И АНАЛИТИКА</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

            "📈 <b>КАЧЕСТВО ОТВЕТОВ</b>\n"
            "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
            "✦ BLEU Score — точность генерации\n"
            "✦ Semantic Similarity — смысловое сходство\n"
            "✦ LLM-as-a-Judge — автооценка качества\n\n"

            "🔬 <b>A/B ТЕСТИРОВАНИЕ</b>\n"
            "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
            "✦ Welch's t-test — статистика\n"
            "✦ Cohen's d — размер эффекта\n"
            "✦ Автоматические рекомендации\n\n"

            "📉 <b>МОНИТОРИНГ</b>\n"
            "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
            "✦ Latency — время ответа LLM\n"
            "✦ Token Usage — расход токенов\n"
            "✦ Error Rate — частота ошибок\n\n"

            "🔗 Откройте <b>[Графики]</b> в меню для\n"
            "интерактивного дашборда метрик.\n"
        )
        keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data='help_back')]]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

    elif data == 'help_author':
        text = (
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "👨‍💻 <b>О РАЗРАБОТЧИКЕ</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

            "   <b>Almaz</b>\n"
            "   AI/ML Engineer\n\n"

            "🎓 <b>СЕРТИФИКАЦИЯ</b>\n"
            "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
            "✦ Microsoft Learn Certified\n"
            "✦ AI & Machine Learning Specialist\n\n"

            "🔗 <b>ССЫЛКИ</b>\n"
            "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
            "✦ <a href='https://github.com/AlmazPRO7/StdvBot'>GitHub: StdvBot</a>\n"
            "✦ <a href='https://learn.microsoft.com/ru-ru/users/54773151/'>Microsoft Learn Profile</a>\n\n"

            "💡 <b>О ПРОЕКТЕ</b>\n"
            "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
            "Демонстрационный AI-ассистент для\n"
            "строительного ритейла. Показывает\n"
            "возможности Generative AI в бизнесе.\n\n"

            "📫 <b>Open Source</b> — исходный код доступен\n"
            "на GitHub для изучения и развития.\n"
        )
        keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data='help_back')]]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML", disable_web_page_preview=True)

    elif data == 'help_back':
        # Возврат к главному меню справки
        help_text = (
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "📚 <b>СПРАВОЧНЫЙ ЦЕНТР</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

            "🤖 <b>Что умеет этот бот?</b>\n"
            "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
            "Интеллектуальный помощник для клиентов\n"
            "строительного магазина «Строительный Двор»\n\n"

            "📋 <b>БЫСТРЫЕ КОМАНДЫ</b>\n"
            "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
            "• /start — Перезапуск бота\n"
            "• 📂 <b>Пример CSV</b> — Батч-анализ данных\n"
            "• 📷 <b>Анализ Фото</b> — Распознание товаров\n"
            "• 🎤 <b>Голосовой вопрос</b> — Голосовые запросы\n\n"

            "👇 <b>Выберите раздел справки:</b>"
        )
        keyboard = [
            [InlineKeyboardButton("👔 Бизнес-возможности", callback_data='help_manager')],
            [InlineKeyboardButton("🛠 Техническая архитектура", callback_data='help_tech')],
            [InlineKeyboardButton("📊 Метрики и аналитика", callback_data='help_metrics')],
            [InlineKeyboardButton("👨‍💻 О разработчике", callback_data='help_author')]
        ]
        await query.message.edit_text(help_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
    
    # --- BUSINESS ACTIONS ---
    elif data == 'action_refund':
        await query.message.edit_text(
            f"✅ <b>АВТОВОЗВРАТ ОФОРМЛЕН</b>\n"
            f"Уведомление отправлено клиенту {html.escape(Config.CLIENT_USER)}.\n"
            "<i>Тикет закрыт.</i>",
            parse_mode="HTML"
        )
    
    elif data == 'action_blame':
        await query.message.edit_text("🤬 Генерирую разнос для менеджера...")
        blame_letter = clean_response(ai_client.generate(BLAME_SYSTEM_PROMPT, "Клиент недоволен сервисом"))
        
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"📨 <b>ПИСЬМО МЕНЕДЖЕРУ ({html.escape(Config.MANAGER_USER)}):</b>\n\n{blame_letter}",
            parse_mode="HTML"
        )
        await query.message.delete()
    
    elif data == 'action_ignore':
        await query.message.delete()

async def process_user_message(text: str, update: Update, context: ContextTypes.DEFAULT_TYPE, message_id: int):
    """Единая логика обработки текстовых запросов (от текста или голоса)"""
    chat_id = update.effective_chat.id
    msg = await context.bot.send_message(chat_id=chat_id, text="🧠 Анализирую...")

    try:
        analysis = ai_client.generate_json(ANALYST_SYSTEM_PROMPT, text)
        intent = analysis.get("intent", "unknown").lower()

        if intent == "complaint":
            await msg.delete()
            reply = clean_response(ai_client.generate(SUPPORT_AGENT_SYSTEM_PROMPT, text))

            # SAVE CONTEXT FOR JUDGE
            context.user_data['last_interaction'] = {'question': text, 'answer': reply}

            keyboard = [
                [InlineKeyboardButton("✅ Автовозврат", callback_data='action_refund')],
                [InlineKeyboardButton("🤬 Наказать менеджера", callback_data='action_blame')],
                [InlineKeyboardButton("❌ Игнор", callback_data='action_ignore')]
            ]

            response_msg = await context.bot.send_message(
                chat_id=chat_id,
                text=f"🚨 <b>ИНЦИДЕНТ (Жалоба)</b>\n\n"
                     f"Текст: {html.escape(text)}\n\n"
                     f"📩 <b>Предлагаемый ответ:</b>\n{reply}",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="HTML",
                disable_web_page_preview=True
            )
            # Жалоба - PERMANENT (важный ответ с действиями)
            await mark_permanent(chat_id, response_msg.message_id)

        elif intent in ["sales", "urgent_need"]:
            await msg.delete()
            reply = clean_response(ai_client.generate(UNIVERSAL_AGENT_SYSTEM_PROMPT, f"Клиент хочет купить: {text}"))
            context.user_data['last_interaction'] = {'question': text, 'answer': reply}

            response_msg = await context.bot.send_message(
                chat_id=chat_id,
                text=f"🛒 <b>Продажа/Наличие</b>\n\n{reply}",
                parse_mode="HTML",
                disable_web_page_preview=True
            )
            # Продажа - PERMANENT (важный ответ)
            await mark_permanent(chat_id, response_msg.message_id)

        elif intent == "tech_support":
            await msg.delete()
            reply = clean_response(ai_client.generate(VISION_SYSTEM_PROMPT, f"Дай технический совет: {text}"))
            context.user_data['last_interaction'] = {'question': text, 'answer': reply}

            response_msg = await context.bot.send_message(
                chat_id=chat_id,
                text=f"🔧 <b>Экспертный совет</b>\n\n{reply}",
                parse_mode="HTML",
                disable_web_page_preview=True
            )
            # Техподдержка - PERMANENT (важный ответ)
            await mark_permanent(chat_id, response_msg.message_id)

        elif intent == "policy_question":
            await msg.delete()
            # 1. RAG Retrieval
            context_data = rag_system.retrieve(text)

            # 2. Augmented Generation
            rag_prompt = f"{POLICY_AGENT_SYSTEM_PROMPT}\n\n[CONTEXT]\n{context_data}"
            reply = clean_response(ai_client.generate(rag_prompt, text))

            context.user_data['last_interaction'] = {'question': text, 'answer': reply}

            response_msg = await context.bot.send_message(
                chat_id=chat_id,
                text=f"📜 <b>Правила и Сервис</b>\n\n{reply}\n\n<i>(Ответ сформирован на основе Базы Знаний)</i>",
                parse_mode="HTML",
                disable_web_page_preview=True
            )
            # Политика - PERMANENT (важный ответ)
            await mark_permanent(chat_id, response_msg.message_id)

        else:
            await msg.edit_text(f"📊 <b>{html.escape(intent.upper())}</b>\n{analysis.get('summary')}", parse_mode="HTML", disable_web_page_preview=True)
            # Обычный анализ - можно удалить при следующем действии
            await mark_for_delete(context, chat_id, msg.message_id)

    except Exception as e:
        await msg.edit_text(f"❌ Error: {str(e)}")
        await mark_for_delete(context, chat_id, msg.message_id)

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    chat_id = update.effective_chat.id

    # Удаляем предыдущие временные сообщения при новом действии
    await cleanup_previous(context, chat_id)

    # Помечаем сообщение пользователя для удаления
    await mark_for_delete(context, chat_id, update.message.message_id)

    if text == "📂 Пример CSV":
        demo_path = "data/demo/golden_dataset_full.csv"
        if os.path.exists(demo_path):
            doc_msg = await update.message.reply_document(document=open(demo_path, 'rb'), caption="📥 <b>GOLDEN DATASET</b>", parse_mode="HTML")
            await mark_permanent(chat_id, doc_msg.message_id)  # Документ - permanent
        return
    elif text == "📷 Анализ Фото":
        msg = await update.message.reply_text("📷 <b>Пришли фото для анализа</b>", parse_mode="HTML")
        await mark_for_delete(context, chat_id, msg.message_id)  # Подсказка - временная
        return
    elif text == "🎤 Голосовой вопрос":
        msg = await update.message.reply_text("🎙️ <b>Запиши голосовое сообщение</b> (нажми на микрофон)", parse_mode="HTML")
        await mark_for_delete(context, chat_id, msg.message_id)  # Подсказка - временная
        return
    elif text == "🆘 Справка":
        await help_handler(update, context)
        return

    await process_user_message(text, update, context, update.message.message_id)

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    # Удаляем предыдущие временные сообщения
    await cleanup_previous(context, chat_id)

    # Фото пользователя - для удаления
    await mark_for_delete(context, chat_id, update.message.message_id)

    photo_file = await update.message.photo[-1].get_file()
    msg = await update.message.reply_text("👁️ <b>Анализирую изображение...</b>", parse_mode="HTML")

    try:
        image_bytes = await photo_file.download_as_bytearray()
        response = clean_response(ai_client.generate_with_image(VISION_SYSTEM_PROMPT, update.message.caption or "", image_bytes))

        context.user_data['last_interaction'] = {'question': "Photo Analysis", 'answer': response}

        await msg.edit_text(response, parse_mode="HTML", disable_web_page_preview=True)
        # Ответ на фото - PERMANENT (важный ответ)
        await mark_permanent(chat_id, msg.message_id)
    except Exception as e:
        await msg.edit_text(f"❌ Ошибка: {e}")
        await mark_for_delete(context, chat_id, msg.message_id)  # Ошибка - временная

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    # Удаляем предыдущие временные сообщения
    await cleanup_previous(context, chat_id)

    # Голосовое пользователя - для удаления
    await mark_for_delete(context, chat_id, update.message.message_id)

    voice_file = await update.message.voice.get_file()
    msg = await update.message.reply_text("🎤 <b>Слушаю...</b>", parse_mode="HTML")

    try:
        voice_bytes = await voice_file.download_as_bytearray()

        # --- DEMO HACK: EMPTY VOICE TRIGGER ---
        if len(voice_bytes) < 15000:
            await msg.delete()
            demo_text = "Здравствуйте! Мне нужно 10 листов гипсокартона, профиль для гипсокартона 27 на 28 - 20 штук и саморезы для гипсокартона 3,5 на 25 - 1 килограмм."
            demo_msg = await context.bot.send_message(chat_id=chat_id, text=f"🗣️ <b>Ответ на голосовое:</b>\n<i>(Распознано как):</i> {demo_text}", parse_mode="HTML")
            await mark_permanent(chat_id, demo_msg.message_id)  # Ответ - permanent
            await process_user_message(demo_text, update, context, update.message.message_id)
            return

        response = clean_response(ai_client.generate_with_audio(UNIVERSAL_AGENT_SYSTEM_PROMPT, voice_bytes))

        context.user_data['last_interaction'] = {'question': "Voice Message", 'answer': response}

        await msg.edit_text(f"🗣️ <b>Ответ на голосовое:</b>\n\n{response}", parse_mode="HTML", disable_web_page_preview=True)
        # Ответ на голосовое - PERMANENT
        await mark_permanent(chat_id, msg.message_id)
    except Exception as e:
        await msg.edit_text(f"❌ Ошибка: {str(e)}")
        await mark_for_delete(context, chat_id, msg.message_id)  # Ошибка - временная

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    # Удаляем предыдущие временные сообщения при новом действии
    await cleanup_previous(context, chat_id)

    # Помечаем документ пользователя для удаления
    await mark_for_delete(context, chat_id, update.message.message_id)

    document = update.message.document
    if not document.file_name.endswith('.csv'):
        temp_msg = await update.message.reply_text("⚠️ Только CSV.")
        await mark_for_delete(context, chat_id, temp_msg.message_id)
        return

    status_msg = await update.message.reply_text("📥 Загрузка...")
    new_file = await context.bot.get_file(document.file_id)
    file_path = f"data/{document.file_name}"
    await new_file.download_to_drive(file_path)

    try:
        df = pd.read_csv(file_path)
        text_col = df.columns[0]
        texts = df[text_col].dropna().tolist()
        results = []
        limit = 15
        for i, text in enumerate(texts[:limit]):
            if i%3==0: await status_msg.edit_text(f"⏳ {i}/{limit}...")
            time.sleep(1.5)
            analysis = ai_client.generate_json(ANALYST_SYSTEM_PROMPT, str(text))
            results.append({**analysis, "text": text})

        pd.DataFrame(results).to_csv(f"data/analyzed_{document.file_name}", index=False)
        await status_msg.delete()

        img = create_dashboard(pd.DataFrame(results))
        final_msg = await update.message.reply_photo(photo=img, caption="✅ <b>Отчет готов!</b>", parse_mode="HTML")
        doc_msg = await update.message.reply_document(document=open(f"data/analyzed_{document.file_name}", 'rb'))

        # Отчёты - PERMANENT (важные результаты)
        await mark_permanent(chat_id, final_msg.message_id)
        await mark_permanent(chat_id, doc_msg.message_id)

    except Exception as e:
        await status_msg.edit_text(f"❌ Error: {str(e)}")
        await mark_for_delete(context, chat_id, status_msg.message_id)

async def post_init(application):
    """Установка команд бота при запуске (чистит старые команды)"""
    # 1. Принудительно удаляем ВСЕ старые команды из кэша Telegram
    await application.bot.delete_my_commands()
    
    # 2. Устанавливаем только одну актуальную команду
    await application.bot.set_my_commands([
        ("start", "🚀 Главное меню / Перезапуск")
    ])

if __name__ == '__main__':
    app = ApplicationBuilder().token(Config.TELEGRAM_TOKEN).post_init(post_init).build()
    app.add_handler(CommandHandler("start", start))
    # Removed admin command per request
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_text))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    print("🤖 Construction AI Bot Started...")
    app.run_polling()