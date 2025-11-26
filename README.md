# ConstructionAI Bot

**AI-помощник для строительного ритейла** — интеллектуальный Telegram-бот на базе Google Gemini для автоматизации клиентской поддержки.

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://python.org)
[![Telegram Bot API](https://img.shields.io/badge/Telegram-Bot%20API-blue.svg)](https://core.telegram.org/bots/api)
[![Google Gemini](https://img.shields.io/badge/Google-Gemini%202.0-orange.svg)](https://ai.google.dev/)
[![Cloudflare](https://img.shields.io/badge/Cloudflare-Tunnel-F38020.svg)](https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

---

## Возможности

### Multi-Agent Architecture
- **Analyst Agent** — классификация интентов (жалоба/продажа/вопрос), анализ тональности и срочности
- **Sales Agent** — подбор товаров, поиск в каталоге sdvor.com, генерация ссылок
- **Support Agent** — эмпатичные ответы на жалобы, Brand Safety, готовые действия
- **Vision Agent** — распознавание товаров на фото, поиск аналогов
- **Policy Agent** — ответы на вопросы о правилах и сервисе (RAG)

### Мультимодальность
- **Текст** — естественный язык, вопросы, жалобы
- **Фото** — распознавание товаров через Vision AI
- **Голос** — голосовые сообщения (Whisper AI)
- **CSV** — батч-обработка датасетов

### Enterprise Features
- **Rate Limiting** — 30 запросов/сутки на пользователя (защита от спама)
- **Metrics & Analytics** — сбор статистики использования
- **RAG Search** — поиск по базе знаний (BM25 + TF-IDF)
- **Fallback System** — автопереключение между провайдерами (Gemini → OpenRouter)
- **A/B Testing** — фреймворк для тестирования промптов
- **Web Dashboard** — интерактивная панель аналитики (Flask + Plotly)
- **Cloudflare Tunnel** — публичный доступ к дашборду через trycloudflare.com

---

## Архитектура

```
┌─────────────────────────────────────────────────────────────┐
│                     Telegram Bot API                        │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    telegram_bot.py                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐    │
│  │  /start  │  │  Text    │  │  Photo   │  │  Voice   │    │
│  │  /stats  │  │  Handler │  │  Handler │  │  Handler │    │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘    │
└─────────────────────────────────────────────────────────────┘
         │                    │                      │
         │     ┌──────────────┼──────────────────────┤
         │     ▼              ▼                      ▼
         │ ┌─────────────┐ ┌─────────────┐ ┌─────────────────┐
         │ │ Rate Limiter│ │  LLM Client │ │   RAG Engine    │
         │ │  (30/day)   │ │  (Gemini)   │ │ (BM25+TF-IDF)   │
         │ └─────────────┘ └─────────────┘ └─────────────────┘
         │                        │
         │                        ▼
         │               ┌─────────────┐
         │               │   Prompts   │
         │               │  (Agents)   │
         │               └─────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────┐
│                     Web Dashboard                           │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │ webapp_server│──│  Cloudflared │──│ trycloudflare.com│  │
│  │  (Flask:5000)│  │   (Tunnel)   │  │  (Public URL)    │  │
│  └──────────────┘  └──────────────┘  └──────────────────┘  │
│         │                                                   │
│         ▼                                                   │
│  ┌────────────────────────────────────────────────────┐    │
│  │ Plotly Charts: Confusion Matrix, Latency, A/B Test │    │
│  │ Real-time Logs, Agent Prompts Viewer               │    │
│  └────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

---

## Структура проекта

```
ConstructionAI_System/
├── telegram_bot.py          # Главный файл бота (800+ строк)
├── src/
│   ├── llm_client.py        # Клиент Gemini API + Fallback
│   ├── prompts.py           # Системные промпты агентов
│   ├── rag_engine.py        # RAG система (BM25 + TF-IDF)
│   ├── rate_limiter.py      # Лимит запросов (30/сутки)
│   ├── metrics.py           # Сбор метрик использования
│   ├── config.py            # Конфигурация
│   ├── webapp_server.py     # Web Dashboard (Flask)
│   ├── visualizer.py        # Визуализация аналитики
│   └── templates/
│       └── dashboard.html   # HTML шаблон дашборда
├── cloudflared              # Cloudflare Tunnel бинарник
├── tunnel_url.txt           # Текущий публичный URL туннеля
├── prompt_engineering/
│   ├── ab_testing.py        # A/B тестирование промптов
│   ├── metrics_calculator.py # Расчёт метрик качества
│   └── visualization.py     # Визуализация результатов
├── tests/                   # 18 тестов
├── scripts/                 # CLI и утилиты
├── docs/                    # Документация (13 файлов)
├── data/
│   ├── knowledge_base.txt   # База знаний для RAG
│   └── demo/                # Демо-датасеты
├── Dockerfile               # Контейнеризация
├── docker-compose.yml       # Оркестрация
└── requirements.txt         # Зависимости
```

---

## Команды бота

| Команда | Описание |
|---------|----------|
| `/start` | Главное меню, очистка чата |
| `/stats` | Статистика и лимиты пользователя |

### Кнопки меню

| Кнопка | Функция |
|--------|---------|
| 📂 Пример CSV | Скачать демо-датасет для батч-анализа |
| 📷 Анализ Фото | Распознавание товара на фото |
| 🎤 Голосовой вопрос | Голосовой ввод (Whisper AI) |
| 🆘 Справка | Интерактивная справка |

---

## Установка

### Требования
- Python 3.10+
- Google Cloud аккаунт (для Gemini API)
- Telegram Bot Token

### Быстрый старт

```bash
# 1. Клонировать репозиторий
git clone https://github.com/AlmazPRO7/StdvBot.git
cd StdvBot

# 2. Создать виртуальное окружение
python3 -m venv venv
source venv/bin/activate

# 3. Установить зависимости
pip install -r requirements.txt

# 4. Настроить переменные окружения
cp .env.example .env
# Заполнить: TELEGRAM_BOT_TOKEN, GOOGLE_API_KEY

# 5. Настроить Gemini OAuth (опционально)
gcloud auth application-default login

# 6. Запустить бота
python3 telegram_bot.py
```

### Docker

```bash
# Сборка и запуск
docker-compose up -d

# Логи
docker-compose logs -f bot
```

---

## Конфигурация

### Переменные окружения (.env)

```env
# Telegram
TELEGRAM_BOT_TOKEN=your_bot_token

# AI Provider (gemini/openrouter/auto)
AI_PROVIDER=auto
GOOGLE_API_KEY=your_gemini_key
OPENROUTER_API_KEY=your_openrouter_key

# Контакты для бота
ADMIN_USERNAME=@admin
CLIENT_USERNAME=@client
MANAGER_USERNAME=@manager
```

### Rate Limiting

По умолчанию: **30 запросов в сутки** на пользователя.

Изменить лимит в `src/rate_limiter.py`:
```python
rate_limiter = RateLimiter(max_requests=30)  # Изменить число
```

---

## Метрики

Бот собирает статистику:
- Количество запросов (текст/фото/голос)
- Уникальные пользователи
- Rate-limited запросы
- Ошибки

Данные сохраняются в `data/metrics.json`.

Просмотр: отправить `/stats` боту.

---

## Web Dashboard

Интерактивная панель аналитики с графиками Plotly и публичным доступом через Cloudflare Tunnel.

### Возможности дашборда

| Виджет | Описание |
|--------|----------|
| Confusion Matrix | Точность классификации интентов |
| Latency Chart | График времени отклика |
| A/B Test Results | Сравнение версий промптов |
| RAG Topics | Распределение тем базы знаний |
| Request Logs | Лента последних запросов |
| Agent Prompts | Просмотр системных промптов |

### Запуск дашборда

```bash
# 1. Запустить Flask-сервер (порт 5000)
python3 src/webapp_server.py &

# 2. Запустить Cloudflare Tunnel
./cloudflared tunnel --url http://localhost:5000 > tunnel.log 2>&1 &

# 3. Получить публичный URL
grep -o 'https://[^"]*\.trycloudflare\.com' tunnel.log | head -1 > tunnel_url.txt
cat tunnel_url.txt
```

### Автоинтеграция с ботом

Бот автоматически читает `tunnel_url.txt` при старте и:
- Добавляет кнопку **📊 Dashboard** в меню
- Использует Telegram WebApp для встроенного просмотра
- Автоматически обновляет URL при перезапуске туннеля

```python
# telegram_bot.py (автоподхват URL)
if os.path.exists("tunnel_url.txt"):
    with open("tunnel_url.txt", "r") as f:
        webapp_url = f.read().strip()
```

### Текущий Dashboard

🔗 **Live:** Доступен через кнопку в боте или по URL в `tunnel_url.txt`

---

## Telegram Mini Apps

Бот использует **Telegram Mini Apps (WebApp)** для встроенного отображения дашборда прямо в чате.

### Как это работает

```
┌─────────────────────────────────────────┐
│           Telegram Chat                 │
│  ┌───────────────────────────────────┐  │
│  │  📊 Dashboard (Mini App Button)   │  │
│  └───────────────────────────────────┘  │
│                  │                      │
│                  ▼                      │
│  ┌───────────────────────────────────┐  │
│  │      WebApp Iframe                │  │
│  │  ┌─────────────────────────────┐  │  │
│  │  │   Flask Dashboard           │  │  │
│  │  │   via Cloudflare Tunnel     │  │  │
│  │  └─────────────────────────────┘  │  │
│  └───────────────────────────────────┘  │
└─────────────────────────────────────────┘
```

### Реализация в коде

```python
# Создание кнопки Mini App
from telegram import WebAppInfo, InlineKeyboardButton

webapp_button = InlineKeyboardButton(
    text="📊 Dashboard",
    web_app=WebAppInfo(url=webapp_url)  # URL из tunnel_url.txt
)
```

### Преимущества Mini Apps
- 🚀 **Нативный опыт** — дашборд открывается внутри Telegram
- 🔒 **Безопасность** — HTTPS через Cloudflare Tunnel
- 📱 **Адаптивность** — работает на десктопе и мобильных
- ⚡ **Кэш-бастинг** — URL с timestamp предотвращает кэширование

---

## Документация

| Документ | Описание |
|----------|----------|
| [FALLBACK_MECHANISM.md](docs/FALLBACK_MECHANISM.md) | Система автопереключения провайдеров |
| [PROMPT_ENGINEERING_GUIDE.md](docs/PROMPT_ENGINEERING_GUIDE.md) | Гайд по работе с промптами |
| [VISION_PROMPT_UPDATE.md](docs/VISION_PROMPT_UPDATE.md) | Vision-промпт для фото |
| [README_INTERVIEW.md](docs/README_INTERVIEW.md) | Подготовка к техническому интервью |

---

## Технологии

| Компонент | Технология |
|-----------|------------|
| LLM | Google Gemini 2.0 Flash |
| Fallback LLM | OpenRouter (Claude, GPT-4) |
| Bot Framework | python-telegram-bot 22.x |
| Web Dashboard | Flask + Plotly.js |
| Tunnel | Cloudflare Tunnel (trycloudflare.com) |
| Mini Apps | Telegram WebApp API |
| RAG | BM25 + TF-IDF (scikit-learn) |
| Metrics | BLEU, Semantic Similarity, LLM-as-Judge |
| A/B Testing | Welch's t-test, Cohen's d |
| Контейнеризация | Docker, Docker Compose |

---

## Разработка

### Запуск тестов

```bash
# Все тесты
python -m pytest tests/ -v

# Конкретный тест
python -m pytest tests/test_fallback.py -v
```

### Prompt Engineering CLI

```bash
# Интерактивная демонстрация
python scripts/demo_prompt_engineering.py

# A/B тестирование
python scripts/prompt_engineering_cli.py
```

---

## Скриншоты

<details>
<summary>Главное меню</summary>

Бот приветствует пользователя и показывает возможности:
- Multi-Agent маршрутизация
- RAG поиск по базе знаний
- Vision AI для фото
- Голосовые сообщения

</details>

<details>
<summary>Анализ фото</summary>

Отправьте фото товара — бот:
1. Распознает товар
2. Найдёт в каталоге sdvor.com
3. Покажет цены и аналоги

</details>

---

## Лицензия

MIT License — см. [LICENSE](LICENSE)

---

## Автор

**Almaz** — [GitHub](https://github.com/AlmazPRO7) | [Microsoft Learn](https://learn.microsoft.com/ru-ru/users/54773151/)

---

*Создано как демонстрация возможностей Generative AI в enterprise-сценариях.*
