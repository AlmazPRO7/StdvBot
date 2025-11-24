# ConstructionAI Bot

Telegram-бот с AI для автоматизации поддержки клиентов в сфере стройматериалов.

## Возможности

- **Анализ сообщений** — классификация интентов, определение тональности и срочности (JSON)
- **Vision-анализ** — распознавание товаров на фото и генерация поисковых ссылок
- **Telegram-интеграция** — полнофункциональный бот с поддержкой текста, фото и документов
- **Google Gemini** — использует Gemini 2.0 Flash через OAuth ADC

## Структура проекта

```
ConstructionAI_System/
├── telegram_bot.py        # Главный файл бота
├── src/                   # Исходный код
│   ├── llm_client.py      # Клиент для Gemini API
│   ├── prompts.py         # Системные промпты
│   └── config.py          # Конфигурация
├── tests/                 # Тесты
├── scripts/               # Вспомогательные скрипты
├── docs/                  # Документация
├── prompt_engineering/    # Инструменты для работы с промптами
├── data/                  # Данные (Excel каталог)
└── requirements.txt       # Зависимости
```

## Установка

```bash
# Клонировать репозиторий
git clone https://github.com/AlmazPRO7/StdvBot.git
cd StdvBot

# Создать виртуальное окружение
python3 -m venv venv
source venv/bin/activate

# Установить зависимости
pip install -r requirements.txt

# Настроить переменные окружения
cp .env.example .env
# Заполнить TELEGRAM_BOT_TOKEN
```

## Настройка Gemini OAuth

```bash
# Установить gcloud CLI и авторизоваться
gcloud auth application-default login
```

## Запуск

```bash
source venv/bin/activate
python3 telegram_bot.py
```

## Документация

Подробная документация в папке `docs/`:
- [Механизм Fallback](docs/FALLBACK_MECHANISM.md)
- [Prompt Engineering Guide](docs/PROMPT_ENGINEERING_GUIDE.md)
- [Vision Prompt](docs/VISION_PROMPT_UPDATE.md)

## Технологии

- Python 3.10+
- python-telegram-bot
- Google Gemini 2.0 Flash
- OAuth ADC (Application Default Credentials)
