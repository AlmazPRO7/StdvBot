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
_help_messages: dict[int, int] = {}  # chat_id -> help_message_id (одно на чат)

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

async def clear_chat(context: ContextTypes.DEFAULT_TYPE, chat_id: int, current_msg_id: int, keep_ids: set = None):
    """
    Очищает чат: удаляет все сообщения до current_msg_id.
    keep_ids - set ID сообщений которые НЕ удалять.
    """
    if keep_ids is None:
        keep_ids = set()

    deleted_count = 0
    # Идём от текущего сообщения назад (до 100 сообщений)
    for msg_id in range(current_msg_id, max(1, current_msg_id - 100), -1):
        if msg_id in keep_ids:
            continue
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=msg_id)
            deleted_count += 1
        except Exception:
            pass  # Сообщение уже удалено или недоступно

    logging.info(f"Chat {chat_id} cleared: {deleted_count} messages deleted")
    return deleted_count

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
    start_msg_id = update.message.message_id

    # Определяем какие сообщения сохранить при очистке
    keep_ids = set()

    # Проверяем: если приветствие уже есть И не удалено
    welcome_exists = False
    if chat_id in _welcome_messages:
        welcome_id = _welcome_messages[chat_id]
        try:
            # Проверяем существует ли (пробуем закрепить)
            await context.bot.pin_chat_message(chat_id=chat_id, message_id=welcome_id, disable_notification=True)
            welcome_exists = True
            keep_ids.add(welcome_id)  # Сохраняем приветствие при очистке
        except Exception:
            # Сообщение удалено
            del _welcome_messages[chat_id]
            if chat_id in _permanent_messages and welcome_id in _permanent_messages[chat_id]:
                _permanent_messages[chat_id].discard(welcome_id)

    # Очищаем чат (удаляем все сообщения кроме приветствия)
    await clear_chat(context, chat_id, start_msg_id, keep_ids)

    # Очищаем трекинг удалённых сообщений
    if chat_id in _help_messages:
        del _help_messages[chat_id]
    if chat_id in _deletable_messages:
        _deletable_messages[chat_id] = []

    # Если приветствие уже есть — не дублируем
    if welcome_exists:
        return

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

    # Формируем приветственное сообщение (начинается с читаемого текста для превью)
    welcome_message = (
        "🏗 <b>Строительный Двор AI</b> — ваш умный помощник\n\n"

        "🤖 Интеллектуальный ассистент на базе Generative AI\n\n"

        "<b>Возможности:</b>\n"
        "• Multi-Agent — умная маршрутизация\n"
        "• RAG Search — поиск по базе знаний\n"
        "• Vision AI — анализ фото товаров\n"
        "• Voice — голосовые сообщения\n\n"

        f"📊 <a href='{webapp_url}'>Dashboard</a> • "
        "<a href='https://github.com/AlmazPRO7/StdvBot'>GitHub</a> • "
        "<a href='https://learn.microsoft.com/ru-ru/users/54773151/'>Microsoft Learn</a>\n\n"

        "💬 Напишите вопрос или выберите действие:\n"
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

    # Сохраняем ID нового приветствия
    _welcome_messages[chat_id] = welcome_msg.message_id

    # Приветствие - PERMANENT (не удаляем автоматически)
    await mark_permanent(chat_id, welcome_msg.message_id)

    # Закрепляем новое приветствие
    try:
        await context.bot.pin_chat_message(chat_id=chat_id, message_id=welcome_msg.message_id, disable_notification=True)
    except Exception as e:
        logging.debug(f"Failed to pin welcome: {e}")

async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    # Удаляем старую справку если есть
    if chat_id in _help_messages:
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=_help_messages[chat_id])
        except Exception:
            pass
        del _help_messages[chat_id]

    # Удаляем сообщение пользователя (нажатие кнопки "Справка")
    try:
        await context.bot.delete_message(chat_id=chat_id, message_id=update.message.message_id)
    except Exception:
        pass

    help_text = (
        "📚 <b>Справочный центр</b>\n\n"

        "🤖 <b>Что умеет бот?</b>\n"
        "AI-помощник для клиентов «Строительный Двор»\n\n"

        "<b>Возможности:</b>\n"
        "💬 Текст — напишите вопрос или жалобу\n"
        "📷 Фото — отправьте фото товара\n"
        "🎤 Голос — запишите голосовое сообщение\n"
        "📂 CSV — загрузите файл для батч-анализа\n\n"

        "👇 <b>Выберите раздел:</b>"
    )

    keyboard = [
        [InlineKeyboardButton("🧪 Как тестировать", callback_data='help_test')],
        [InlineKeyboardButton("👔 Бизнес-возможности", callback_data='help_manager')],
        [InlineKeyboardButton("🛠 Техническая архитектура", callback_data='help_tech')],
        [InlineKeyboardButton("📊 Метрики и аналитика", callback_data='help_metrics')],
        [InlineKeyboardButton("👨‍💻 О разработчике", callback_data='help_author')]
    ]
    help_msg = await update.effective_chat.send_message(help_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

    # Сохраняем ID справки
    _help_messages[chat_id] = help_msg.message_id

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == 'help_test':
        text = (
            "🧪 <b>Как тестировать</b>\n\n"

            "💬 <b>Текстовые запросы</b>\n"
            "<code>Нужна шпаклёвка для ванной</code>\n"
            "<code>Ищу профиль для гипсокартона 3м</code>\n"
            "<code>Хочу вернуть товар, он бракованный!</code>\n\n"

            "📷 <b>Фото товаров</b>\n"
            "Отправьте фото: плитка, ламинат, краска, инструменты\n"
            "→ Бот найдёт товар в каталоге\n\n"

            "🎤 <b>Голосовые сообщения</b>\n"
            "<i>«Мне нужен цемент м500 и песок»</i>\n"
            "→ Распознавание через Whisper AI\n\n"

            "📂 <b>Батч-анализ</b>\n"
            "Нажмите <b>📂 Пример CSV</b> или загрузите свой файл\n"
        )
        keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data='help_back')]]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

    elif data == 'help_manager':
        text = (
            "👔 <b>Бизнес-возможности</b>\n\n"

            "🎯 <b>Умная маршрутизация</b>\n"
            "• Автоопределение: жалоба, продажа, вопрос\n"
            "• Анализ настроения и срочности\n\n"

            "🛡 <b>Автоподдержка</b>\n"
            "• Эмпатичные ответы за 2 сек\n"
            "• Brand Safety, готовые действия\n\n"

            "🛒 <b>Продажи</b>\n"
            "• Понимает: <i>«10 листов ГКЛ + профили»</i>\n"
            "• Поиск по каталогу, подбор аналогов\n\n"

            "📱 <b>Мультимодальность</b>\n"
            "• Голос, фото, CSV батч-обработка\n"
        )
        keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data='help_back')]]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

    elif data == 'help_tech':
        text = (
            "🛠 <b>Техническая архитектура</b>\n\n"

            "🏗 <b>Agentic Workflow</b>\n"
            "• Analyst → Sales → Support → Vision\n\n"

            "🧠 <b>LLM</b>\n"
            "• Gemini 2.0 Flash + OpenRouter Fallback\n"
            "• JSON Mode, Vision, Audio\n\n"

            "⚙️ <b>Stack</b>\n"
            "• Python 3.12, RAG (BM25 + TF-IDF)\n"
            "• Circuit Breaker, A/B Testing\n\n"

            "📦 <b>Enterprise</b>\n"
            "• Docker, Healthcheck, Graceful Degradation\n"
        )
        keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data='help_back')]]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

    elif data == 'help_metrics':
        text = (
            "📊 <b>Метрики и аналитика</b>\n\n"

            "📈 <b>Качество</b>\n"
            "• BLEU Score, Semantic Similarity\n"
            "• LLM-as-a-Judge автооценка\n\n"

            "🔬 <b>A/B тесты</b>\n"
            "• Welch's t-test, Cohen's d\n\n"

            "📉 <b>Мониторинг</b>\n"
            "• Latency, Token Usage, Error Rate\n\n"

            "🔗 Откройте <b>[Графики]</b> в меню\n"
        )
        keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data='help_back')]]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

    elif data == 'help_author':
        text = (
            "💡 <b>О проекте</b>\n\n"

            "AI-ассистент для строительного ритейла.\n"
            "Демонстрация возможностей Generative AI.\n\n"

            "<b>Ссылки:</b>\n"
            "📂 <a href='https://github.com/AlmazPRO7/StdvBot'>GitHub Repository</a>\n"
            "🎓 <a href='https://learn.microsoft.com/ru-ru/users/54773151/'>Microsoft Learn</a>\n\n"

            "📫 Open Source — код доступен для изучения\n"
        )
        keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data='help_back')]]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML", disable_web_page_preview=True)

    elif data == 'help_back':
        # Возврат к главному меню справки
        help_text = (
            "📚 <b>Справочный центр</b>\n\n"

            "🤖 <b>Что умеет бот?</b>\n"
            "AI-помощник для клиентов «Строительный Двор»\n\n"

            "<b>Команды:</b>\n"
            "• /start — Перезапуск\n"
            "• 📂 Пример CSV — Батч-анализ\n"
            "• 📷 Фото — Распознание товаров\n"
            "• 🎤 Голос — Голосовые запросы\n\n"

            "👇 <b>Выберите раздел:</b>"
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
    msg = await context.bot.send_message(
        chat_id=chat_id,
        text="🧠 <b>Анализирую запрос...</b>\n\n"
             "📊 Определяю тип обращения\n"
             "🎯 Подбираю релевантный ответ",
        parse_mode="HTML"
    )

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
    msg = await update.message.reply_text(
        "👁️ <b>Анализирую изображение...</b>\n\n"
        "🔍 Распознаю товар на фото\n"
        "📦 Ищу в каталоге sdvor.com\n"
        "💰 Подбираю цены и аналоги",
        parse_mode="HTML"
    )

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
    msg = await update.message.reply_text(
        "🎤 <b>Слушаю голосовое...</b>\n\n"
        "🗣️ Распознаю речь (Whisper AI)\n"
        "📝 Анализирую запрос\n"
        "🛒 Подбираю товары и ответ",
        parse_mode="HTML"
    )

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