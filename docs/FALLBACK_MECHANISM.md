# Fallback Механизм: OpenRouter → Google Gemini API

**Дата добавления:** 22.11.2025
**Версия:** 1.0

---

## 📋 Описание

Автоматическая система переключения с OpenRouter на прямой Google Gemini API при исчерпании rate limits.

### Проблема

OpenRouter бесплатный tier:
- **50 запросов/день** на каждый API ключ
- При активном использовании бота лимиты быстро исчерпываются
- Бот возвращает `Error: Failed after 12 attempts` пользователям

### Решение

**Гибридный подход:**
1. **Primary:** OpenRouter (4 ключа × 50 = 200 запросов/день)
2. **Fallback:** Google Gemini Direct API (1500 запросов/день, бесплатно)

---

## 🔧 Как работает

### Архитектура

```python
GeminiClient (главный класс)
  ├─ OpenRouterManager (4 API ключа)
  │   └─ Ротация ключей при 429
  │
  └─ GeminiDirectClient (fallback)
      └─ OAuth через Application Default Credentials
```

### Flow диаграмма

```
Пользователь отправляет запрос
    ↓
GeminiClient._execute()
    ↓
Попытка #1: OpenRouter key #1
    ├─ ✅ 200 → Возвращаем ответ
    └─ ❌ 429 → rate_limit_count++, rotate_key()
    ↓
Попытка #2: OpenRouter key #2
    └─ ❌ 429 → rate_limit_count++, rotate_key()
    ↓
Попытка #3: OpenRouter key #3
    └─ ❌ 429 → rate_limit_count++, rotate_key()
    ↓
Попытка #4: OpenRouter key #4
    └─ ❌ 429 → rate_limit_count++, rotate_key()
    ↓
rate_limit_count >= 4 (ВСЕ ключи исчерпаны)
    ↓
🔄 FALLBACK на Gemini Direct API
    ├─ ✅ 200 → Возвращаем ответ
    └─ ❌ Error → Продолжаем retry OpenRouter
```

---

## ✅ Протестированные сценарии

### Тест 1: Текстовый запрос ✅

**Запрос:** "Напиши одно предложение про строительные материалы."

**Результат:**
```
🔄 All OpenRouter keys rate limited. Switching to Gemini Direct API...
✅ PASSED: Строительные материалы - это основа любого здания...
```

**Время:** ~16 секунд (4 ключа × 4s retry + 1s Gemini)

---

### Тест 2: Vision запрос ✅

**Запрос:** Изображение 300x200 (зелёный фон + текст "FALLBACK TEST")

**Результат:**
```
🔄 All OpenRouter keys rate limited. Switching to Gemini Direct API...
✅ PASSED: На картинке изображен зеленый фон с надписью "FALLBACK TEST"...
```

**Время:** ~14 секунд

---

### Тест 3: JSON запрос ⚠️

**Статус:** Частично работает

**Проблема:** Gemini API не поддерживает `response_format: {type: "json_object"}`

**Workaround:** Добавлен в промпт текст "ВАЖНО: Ответ СТРОГО в формате JSON"

**Примечание:** Для критичных JSON запросов рекомендуется добавить кредиты на OpenRouter

---

## 🚀 Установка

### Требования

1. **Google Cloud SDK настроен:**
   ```bash
   gcloud auth application-default login
   ```

2. **Python пакеты:**
   ```bash
   pip install google-auth google-auth-oauthlib
   ```

### Проверка

```bash
# Проверить ADC credentials
ls ~/.config/gcloud/application_default_credentials.json

# Запустить тест fallback
python3 test_fallback.py
```

**Ожидаемый output:**
```
✅ Gemini Direct API fallback enabled
🔄 All OpenRouter keys rate limited. Switching to Gemini Direct API...
✅ TEXT: PASSED
✅ VISION: PASSED
```

---

## 📊 Сравнение провайдеров

| Параметр | OpenRouter | Gemini Direct |
|----------|------------|---------------|
| **Лимиты** | 50 req/день (×4 = 200) | 1500 req/день |
| **Стоимость** | Бесплатно / $5-10 за 1000 | Бесплатно |
| **Vision** | ✅ Поддерживается | ✅ Поддерживается |
| **JSON mode** | ✅ Нативно | ⚠️ Через промпт |
| **Авторизация** | API ключ | OAuth ADC |
| **Скорость** | ~0.3s | ~0.8s |
| **Fallback** | Нет | N/A (основной при 429) |

---

## 🛠️ Конфигурация

### src/llm_client.py

```python
# Инициализация fallback при старте
if GEMINI_AVAILABLE:
    self.gemini_fallback = GeminiDirectClient()
    logger.info("✅ Gemini Direct API fallback enabled")

# Активация при 429 на всех ключах
if rate_limit_count >= len(self.manager.keys) and self.gemini_fallback:
    logger.warning("🔄 All OpenRouter keys rate limited. Switching to Gemini Direct API...")
    return self.gemini_fallback.generate(system_prompt, user_text, temperature)
```

---

## 📝 Логи

### Нормальная работа (OpenRouter доступен)

```
2025-11-22 15:00:00 - INFO - 🔑 Loaded 4 OpenRouter keys
2025-11-22 15:00:00 - INFO - ✅ Gemini Direct API fallback enabled
2025-11-22 15:00:01 - INFO - Request successful (HTTP 200)
```

### Fallback активирован

```
2025-11-22 15:10:19 - WARNING - ⚠️ Rate Limit (429) on key ending ...7c4dd
2025-11-22 15:10:22 - WARNING - ⚠️ Rate Limit (429) on key ending ...ba1cb
2025-11-22 15:10:26 - WARNING - ⚠️ Rate Limit (429) on key ending ...c82d3
2025-11-22 15:10:30 - WARNING - ⚠️ Rate Limit (429) on key ending ...6fe80
2025-11-22 15:10:32 - WARNING - 🔄 All OpenRouter keys rate limited. Switching to Gemini Direct API...
2025-11-22 15:10:34 - INFO - Gemini Direct API: Request successful
```

---

## ⚡ Performance

### Задержка при fallback

- **OpenRouter (4 ключа × 4s retry):** ~16 секунд
- **Gemini API request:** ~1 секунда
- **TOTAL:** ~17 секунд до первого успешного ответа

### Оптимизация (будущее)

**Идея:** Уменьшить max_retries с 12 до 4 (только по одной попытке на каждый ключ)

```python
max_retries = len(self.manager.keys)  # 4 вместо 12
```

**Эффект:** Задержка сократится с 17s до ~9s

---

## 🆘 Troubleshooting

### Ошибка: "google-auth not installed"

**Решение:**
```bash
pip install google-auth google-auth-oauthlib
```

---

### Ошибка: "Gemini Auth Error"

**Причина:** ADC не настроены

**Решение:**
```bash
gcloud auth application-default login
```

**Проверка:**
```bash
ls ~/.config/gcloud/application_default_credentials.json
```

---

### Fallback не активируется

**Диагностика:**
```bash
python3 -c "from src.llm_client import GEMINI_AVAILABLE; print(GEMINI_AVAILABLE)"
# Должно вернуть: True
```

**Если False:**
```bash
pip install google-auth google-auth-oauthlib
```

---

## 📈 Метрики (примерные)

### Сценарий 1: Низкая нагрузка (<200 req/день)

- **OpenRouter:** 100% запросов
- **Gemini fallback:** 0% (не используется)
- **Средняя задержка:** 0.3s

### Сценарий 2: Средняя нагрузка (200-500 req/день)

- **OpenRouter:** 40% запросов (200 из 500)
- **Gemini fallback:** 60% запросов (300 из 500)
- **Средняя задержка:** 2-3s (включая retry)

### Сценарий 3: Высокая нагрузка (>1500 req/день)

- **OpenRouter:** 13% запросов (200 из 1500)
- **Gemini fallback:** 87% запросов (1300 из 1500)
- **Средняя задержка:** 1-2s (прямо на Gemini после первого круга)

---

## 🎯 Рекомендации

### Для production использования:

1. **Добавить мониторинг:**
   ```python
   # Логировать соотношение OpenRouter / Gemini
   openrouter_count = 0
   gemini_count = 0
   ```

2. **Кэширование:**
   ```python
   # Сохранять частые запросы в Redis
   # Избежать повторных API calls
   ```

3. **Rate limiting на стороне бота:**
   ```python
   # Лимит 10 запросов/час на пользователя
   # Защита от спама
   ```

---

## 📚 Полезные ссылки

- **OpenRouter Status:** https://openrouter.ai/status
- **Google AI Studio (API ключи):** https://aistudio.google.com/apikey
- **Gemini API Docs:** https://ai.google.dev/docs
- **Тестовые скрипты:**
  - `test_fallback.py` - полный E2E тест
  - `test_gemini_direct.py` - тест только Gemini API
  - `test_text_keys.py` - тест только OpenRouter

---

**Автор:** Claude Code
**Контакт:** @aptekapb
**Лицензия:** MIT
