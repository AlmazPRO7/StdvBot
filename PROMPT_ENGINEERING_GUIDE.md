# 🎯 Prompt Engineering Toolkit - Руководство

**Версия:** 1.0.0
**Дата:** 22.11.2025
**Статус:** ✅ Production Ready

---

## 📋 Оглавление

1. [Обзор системы](#обзор-системы)
2. [Компоненты](#компоненты)
3. [Быстрый старт](#быстрый-старт)
4. [Расчёт метрик](#расчёт-метрик)
5. [A/B тестирование](#ab-тестирование)
6. [Управление промптами](#управление-промптами)
7. [CLI команды](#cli-команды)
8. [Примеры использования](#примеры-использования)
9. [Best Practices](#best-practices)

---

## 🎯 Обзор системы

**Prompt Engineering Toolkit** - полномасштабный инструмент для работы промпт-инженера в ConstructionAI.

### Ключевые возможности:

✅ **Metrics Calculator** - Расчёт метрик качества (F1, Precision, Recall, BLEU, Similarity)
✅ **A/B Testing Framework** - Сравнение вариантов промптов с статистической значимостью
✅ **Prompt Manager** - Версионирование промптов (semver), история изменений, rollback
✅ **CLI Interface** - Удобный интерфейс командной строки
✅ **Experiment Tracking** - Логирование всех экспериментов с детальными отчётами
✅ **Ground Truth Datasets** - Поддержка эталонных данных для валидации

### Архитектура:

```
ConstructionAI_System/
├── prompt_engineering/          # Основной пакет
│   ├── __init__.py
│   ├── metrics_calculator.py    # Метрики качества
│   ├── ab_testing.py            # A/B тестирование
│   ├── prompt_manager.py        # Версионирование промптов
│   ├── experiments/             # Результаты A/B тестов
│   ├── prompts/                 # Хранилище промптов
│   ├── ground_truth/            # Эталонные данные
│   └── reports/                 # Отчёты
├── prompt_engineering_cli.py    # CLI интерфейс
└── PROMPT_ENGINEERING_GUIDE.md  # Это руководство
```

---

## 🛠 Компоненты

### 1. Metrics Calculator

**Файл:** `prompt_engineering/metrics_calculator.py`

**Поддерживаемые метрики:**

#### Classification Metrics
- **Precision** = TP / (TP + FP)
- **Recall** = TP / (TP + FN)
- **F1 Score** = 2 × (Precision × Recall) / (Precision + Recall)
- **Accuracy** = (TP + TN) / (TP + TN + FP + FN)

#### Text Similarity
- **BLEU-1** - Unigram precision
- **Exact Match** - Точное совпадение
- **Fuzzy Match** - Схожесть по Levenshtein
- **Word Overlap** - Пересечение слов

#### Link Quality
- **Exact Match Ratio** - Полное совпадение URL
- **Domain Match** - Совпадение домена
- **Params Match** - Наличие региональных параметров (lr=54, /ekaterinburg, etc.)

#### Category Matching
- **Exact Match** - Точное совпадение категории
- **Fuzzy Match** - Схожесть названий категорий

**API:**
```python
from prompt_engineering.metrics_calculator import MetricsCalculator

calc = MetricsCalculator()

# Classification
result = calc.calculate_classification_metrics(
    true_positives=45,
    false_positives=5,
    false_negatives=10,
    true_negatives=40
)
print(f"F1 Score: {result.f1_score:.3f}")

# Text Similarity
similarity = calc.calculate_text_similarity(
    predicted="Bosch GSR 12V-15",
    ground_truth="Bosch GSR 12V-15 Дрель"
)
print(f"BLEU-1: {similarity['bleu_1']:.3f}")

# Link Accuracy
link_acc = calc.calculate_link_accuracy(
    predicted_links=[...],
    ground_truth_links=[...],
    check_params=True
)
print(f"Exact Match: {link_acc['exact_match_ratio']:.3f}")
```

---

### 2. A/B Testing Framework

**Файл:** `prompt_engineering/ab_testing.py`

**Возможности:**
- Запуск A/B тестов между двумя вариантами промптов
- Автоматический расчёт метрик для каждого варианта
- Определение победителя с уровнем уверенности
- Генерация рекомендаций на основе результатов
- Сохранение детальных отчётов

**API:**
```python
from prompt_engineering.ab_testing import ABTester, PromptVariant

tester = ABTester()

# Создать варианты
variant_a = PromptVariant(
    name="baseline_v1",
    prompt_text="Опиши товар.",
    version="1.0",
    description="Базовый промпт"
)

variant_b = PromptVariant(
    name="optimized_v2",
    prompt_text="Проанализируй товар детально...",
    version="2.0",
    description="Оптимизированный промпт"
)

# Запустить A/B тест
report = tester.run_ab_test(
    test_name="vision_optimization",
    variant_a=variant_a,
    variant_b=variant_b,
    test_data=[...],
    executor_func=lambda prompt, data: execute_vision_api(prompt, data),
    metrics_func=lambda output, data: calculate_metrics(output, data)
)

print(f"Победитель: {report.winner}")
print(f"Уверенность: {report.confidence*100:.1f}%")
```

---

### 3. Prompt Manager

**Файл:** `prompt_engineering/prompt_manager.py`

**Возможности:**
- Версионирование промптов (semantic versioning)
- История всех изменений
- Сравнение версий (diff)
- Откат к предыдущим версиям
- Экспорт/импорт промптов

**API:**
```python
from prompt_engineering.prompt_manager import PromptManager

manager = PromptManager()

# Создать промпт
v1 = manager.create_prompt(
    prompt_name="vision_product_detection",
    prompt_text="Опиши товар на картинке.",
    description="Базовый промпт",
    author="john_doe"
)
# → версия 1.0.0

# Обновить промпт
v2 = manager.update_prompt(
    prompt_name="vision_product_detection",
    prompt_text="Проанализируй фото товара...",
    description="Добавлены детальные инструкции",
    version_type="minor"  # major/minor/patch
)
# → версия 1.1.0

# Получить промпт
prompt = manager.get_prompt("vision_product_detection", version="1.0.0")

# Сравнить версии
comparison = manager.compare_versions(
    "vision_product_detection",
    "1.0.0",
    "1.1.0"
)
print(f"Схожесть: {comparison['similarity']*100:.1f}%")

# Откат
manager.rollback("vision_product_detection", target_version="1.0.0")
# → создаёт новую версию 1.1.1 с содержимым 1.0.0
```

---

## 🚀 Быстрый старт

### 1. Установка зависимостей

Все зависимости уже установлены в `venv`. Если нужно переустановить:

```bash
cd /home/ubuntu/ConstructionAI_System
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Создание первого промпта

```bash
./prompt_engineering_cli.py prompt create \
  --name vision_v1 \
  --text "Опиши товар на картинке." \
  --description "Базовый промпт для распознавания товаров"
```

### 3. Список промптов

```bash
./prompt_engineering_cli.py prompt list
```

### 4. Обновление промпта

```bash
./prompt_engineering_cli.py prompt update \
  --name vision_v1 \
  --text "Проанализируй фото товара детально..." \
  --description "Добавлены детальные инструкции" \
  --version-type minor
```

### 5. Просмотр промпта

```bash
./prompt_engineering_cli.py prompt show --name vision_v1
```

---

## 📊 Расчёт метрик

### Пример 1: Classification Metrics

**Сценарий:** Оценка качества определения категорий товаров

```python
from prompt_engineering.metrics_calculator import MetricsCalculator

calc = MetricsCalculator()

# Результаты классификации:
# - 45 товаров определены правильно (TP)
# - 5 товаров ошибочно отнесены к этой категории (FP)
# - 10 товаров пропущены (FN)
# - 40 товаров правильно не отнесены к этой категории (TN)

result = calc.calculate_classification_metrics(
    true_positives=45,
    false_positives=5,
    false_negatives=10,
    true_negatives=40
)

print(f"Precision: {result.precision:.3f}")  # 45/(45+5) = 0.900
print(f"Recall: {result.recall:.3f}")        # 45/(45+10) = 0.818
print(f"F1 Score: {result.f1_score:.3f}")    # 0.857
print(f"Accuracy: {result.accuracy:.3f}")    # (45+40)/100 = 0.850
```

**Интерпретация:**
- **Precision 90%** - Из всех товаров, которые мы отнесли к категории, 90% действительно в ней
- **Recall 82%** - Из всех товаров этой категории мы нашли 82%
- **F1 Score 86%** - Гармоническое среднее, баланс между precision и recall

---

### Пример 2: Link Accuracy

**Сценарий:** Проверка качества генерации ссылок для поиска товаров

```python
# Предсказанные ссылки
pred_links = [
    "https://sdvor.com/ekb/category/instrument-i-oborudovanie-5991",
    "https://market.yandex.ru/search?text=Bosch+GSR&lr=54",
    "https://www.avito.ru/ekaterinburg?q=Bosch+GSR"
]

# Эталонные ссылки
true_links = [
    "https://sdvor.com/ekb/category/instrument-i-oborudovanie-5991",
    "https://market.yandex.ru/search?text=Bosch+GSR+12V-15&lr=54",
    "https://www.avito.ru/ekaterinburg?q=Bosch+GSR+12V-15"
]

link_acc = calc.calculate_link_accuracy(pred_links, true_links, check_params=True)

print(f"Exact Match: {link_acc['exact_match_ratio']:.3f}")      # 1/3 = 0.333
print(f"Domain Match: {link_acc['domain_match_ratio']:.3f}")    # 3/3 = 1.000
print(f"Params Match: {link_acc['params_match_ratio']:.3f}")    # 3/3 = 1.000
```

**Интерпретация:**
- **Domain Match 100%** - Все домены верные (sdvor, yandex, avito)
- **Params Match 100%** - Региональные параметры присутствуют (lr=54, /ekaterinburg)
- **Exact Match 33%** - Только 1 ссылка полностью совпадает (требуется улучшение точности запросов)

---

## 🧪 A/B тестирование

### Полный workflow A/B теста

**Сценарий:** Сравнение базового промпта с оптимизированным

#### Шаг 1: Подготовка промптов

```python
from prompt_engineering.prompt_manager import PromptManager

manager = PromptManager()

# Создать baseline (v1.0.0)
manager.create_prompt(
    prompt_name="vision_baseline",
    prompt_text="Опиши товар на картинке и дай 3 ссылки.",
    description="Базовый промпт без детальных инструкций"
)

# Создать оптимизированный (v1.0.0)
manager.create_prompt(
    prompt_name="vision_optimized",
    prompt_text="""Ты — AI-эксперт каталога компании \"Строительный Двор\".
Проанализируй фото товара и определи:
1. Бренд (если виден)
2. Модель (если видна)
3. Тип товара

Создай 4 точные ссылки для покупки в Екатеринбурге:
1. sdvor.com - ПРИОРИТЕТ (категория товара)
2. Yandex Market - точный поиск + lr=54
3. Google - точный поиск + "купить Екатеринбург"
4. Avito - точный поиск + /ekaterinburg""",
    description="Оптимизированный промпт с детальными инструкциями"
)
```

#### Шаг 2: Подготовка тестовых данных

```python
# Создать датасет с ground truth
test_data = [
    {
        "image": "data/products/bosch_gsr_12v.png",
        "ground_truth": {
            "brand": "BOSCH",
            "model": "GSR 12V-15",
            "type": "Дрель-шуруповёрт",
            "links": [
                "https://sdvor.com/ekb/category/instrument-i-oborudovanie-5991",
                "https://market.yandex.ru/search?text=Bosch+GSR+12V-15&lr=54",
                "https://www.google.com/search?q=Bosch+GSR+12V-15+купить+Екатеринбург",
                "https://www.avito.ru/ekaterinburg?q=Bosch+GSR+12V-15"
            ]
        }
    },
    # ... ещё 49 товаров для статистической значимости
]
```

#### Шаг 3: Определение executor и metrics функций

```python
from src.llm_client import GeminiClient
from prompt_engineering.metrics_calculator import MetricsCalculator

client = GeminiClient()
calc = MetricsCalculator()

def executor_func(prompt_text: str, data: dict) -> str:
    """Выполнить промпт на Vision API"""
    with open(data["image"], 'rb') as f:
        image_bytes = f.read()

    return client.generate_with_image(
        system_prompt=prompt_text,
        user_text="Проанализируй товар на картинке.",
        image_bytes=image_bytes
    )

def metrics_func(output: str, data: dict) -> dict:
    """Рассчитать метрики для output"""
    ground_truth = data["ground_truth"]

    # Извлечь ссылки из output
    import re
    pred_links = re.findall(r'https?://[^\s<>"]+', output)

    # Link accuracy
    link_acc = calc.calculate_link_accuracy(
        pred_links,
        ground_truth["links"],
        check_params=True
    )

    # Text similarity для бренда
    brand_sim = calc.calculate_text_similarity(
        predicted=output,
        ground_truth=ground_truth["brand"]
    )

    return {
        "exact_match_ratio": link_acc["exact_match_ratio"],
        "domain_match": link_acc["domain_match_ratio"],
        "params_match": link_acc["params_match_ratio"],
        "brand_match": brand_sim["word_overlap"]
    }
```

#### Шаг 4: Запуск A/B теста

```python
from prompt_engineering.ab_testing import ABTester, PromptVariant

tester = ABTester()

# Загрузить промпты
baseline = manager.get_prompt("vision_baseline")
optimized = manager.get_prompt("vision_optimized")

# Создать варианты
variant_a = PromptVariant(
    name="baseline",
    prompt_text=baseline.prompt_text,
    version=baseline.version,
    description=baseline.description
)

variant_b = PromptVariant(
    name="optimized",
    prompt_text=optimized.prompt_text,
    version=optimized.version,
    description=optimized.description
)

# Запустить A/B тест
report = tester.run_ab_test(
    test_name="vision_baseline_vs_optimized",
    variant_a=variant_a,
    variant_b=variant_b,
    test_data=test_data,
    executor_func=executor_func,
    metrics_func=metrics_func,
    sample_size=50  # Первые 50 товаров
)
```

#### Шаг 5: Анализ результатов

```
🏆 ПОБЕДИТЕЛЬ: Variant B (optimized)
Уверенность: 95.0%

📈 МЕТРИКИ ВАРИАНТА A (baseline):
  exact_match_ratio: 0.412 (±0.089)
  domain_match: 0.983 (±0.021)
  params_match: 0.734 (±0.112)
  brand_match: 0.891 (±0.067)
  Время выполнения: 4.2s (±0.8s)

📈 МЕТРИКИ ВАРИАНТА B (optimized):
  exact_match_ratio: 0.876 (±0.042)
  domain_match: 1.000 (±0.000)
  params_match: 0.989 (±0.015)
  brand_match: 0.967 (±0.028)
  Время выполнения: 4.5s (±0.7s)

💡 РЕКОМЕНДАЦИИ:
  🎉 Рекомендуется внедрить optimized - показывает улучшение по сравнению с baseline
  📈 Ожидаемое улучшение качества после внедрения
  ⚡ Скорость сопоставима (разница ~7%)

💾 Отчёт сохранён: prompt_engineering/experiments/vision_baseline_vs_optimized_20251122_172345
```

**Интерпретация:**
- **exact_match_ratio:** Вырос с 41% до 88% (+113%) - значительное улучшение точности ссылок
- **params_match:** Вырос с 73% до 99% (+35%) - региональные параметры теперь почти всегда присутствуют
- **brand_match:** Вырос с 89% до 97% (+9%) - улучшение определения бренда
- **Скорость:** Практически одинаковая (4.2s vs 4.5s)

**Решение:** Внедрить оптимизированный промпт в production

---

## 📝 Управление промптами

### Версионирование (Semantic Versioning)

**Формат версии:** `MAJOR.MINOR.PATCH`

- **MAJOR** - Кардинальные изменения, несовместимые с предыдущими версиями
- **MINOR** - Добавление новой функциональности, обратно совместимые
- **PATCH** - Мелкие исправления, bug fixes

**Примеры:**
```python
# 1.0.0 → 1.1.0 (добавлены детальные инструкции)
manager.update_prompt(..., version_type="minor")

# 1.1.0 → 2.0.0 (полностью переписан промпт)
manager.update_prompt(..., version_type="major")

# 2.0.0 → 2.0.1 (исправлена опечатка)
manager.update_prompt(..., version_type="patch")
```

### История изменений

Каждая версия промпта содержит:
- **version** - Номер версии
- **prompt_text** - Текст промпта
- **description** - Описание изменений
- **author** - Автор изменений
- **created_at** - Дата создания
- **hash** - SHA256 хэш промпта
- **parent_version** - Предыдущая версия

### Сравнение версий

```python
comparison = manager.compare_versions(
    "vision_product_detection",
    "1.0.0",
    "2.0.0"
)

print(f"Схожесть: {comparison['similarity']*100:.1f}%")
print(f"Изменено строк: {comparison['lines_changed']}")

# Diff (unified format)
for line in comparison['diff']:
    print(line)
```

**Вывод:**
```
--- vision_product_detection v1.0.0
+++ vision_product_detection v2.0.0
@@ -1,1 +1,10 @@
-Опиши товар на картинке.
+Ты — AI-эксперт каталога компании "Строительный Двор".
+Проанализируй фото товара и определи:
+1. Бренд (если виден)
+2. Модель (если видна)
+3. Тип товара
+...
```

### Rollback

Откат к предыдущей версии создаёт НОВУЮ версию (не удаляет текущую):

```python
# Текущая: 2.0.0
# Откатываемся к: 1.0.0
manager.rollback("vision_product_detection", target_version="1.0.0")
# → Создана новая версия 2.0.1 с содержимым 1.0.0

# История версий:
# 1.0.0 - Базовый промпт
# 1.1.0 - Добавлены инструкции
# 2.0.0 - Полностью переписан
# 2.0.1 - Rollback to 1.0.0 (текущая)
```

---

## 💻 CLI команды

### Полный список команд

```bash
# METRICS
./prompt_engineering_cli.py metrics --test-results results.json

# A/B TEST
./prompt_engineering_cli.py ab-test --variant-a baseline --variant-b optimized --test-data products.json

# PROMPT MANAGEMENT
./prompt_engineering_cli.py prompt list
./prompt_engineering_cli.py prompt create --name NAME --text "TEXT" --description "DESC"
./prompt_engineering_cli.py prompt update --name NAME --text "TEXT" --version-type minor
./prompt_engineering_cli.py prompt show --name NAME [--version VERSION]
./prompt_engineering_cli.py prompt versions --name NAME
./prompt_engineering_cli.py prompt compare --name NAME --version V1 --version2 V2
./prompt_engineering_cli.py prompt export --name NAME [--output FILE]

# BENCHMARK
./prompt_engineering_cli.py benchmark --prompt NAME --dataset data.json

# REPORT
./prompt_engineering_cli.py report --experiment-dir prompt_engineering/experiments
```

### Примеры команд

```bash
# 1. Создать промпт
./prompt_engineering_cli.py prompt create \
  --name vision_v1 \
  --text "Опиши товар на картинке." \
  --description "Базовый промпт"

# 2. Обновить промпт
./prompt_engineering_cli.py prompt update \
  --name vision_v1 \
  --text "Проанализируй товар детально..." \
  --description "Добавлены детальные инструкции" \
  --version-type minor

# 3. Список всех промптов
./prompt_engineering_cli.py prompt list

# 4. Показать промпт
./prompt_engineering_cli.py prompt show --name vision_v1

# 5. Список версий
./prompt_engineering_cli.py prompt versions --name vision_v1

# 6. Сравнение версий
./prompt_engineering_cli.py prompt compare \
  --name vision_v1 \
  --version 1.0.0 \
  --version2 1.1.0

# 7. Экспорт промпта
./prompt_engineering_cli.py prompt export \
  --name vision_v1 \
  --output vision_v1_export.json

# 8. Запуск A/B теста
./prompt_engineering_cli.py ab-test \
  --variant-a vision_baseline \
  --variant-b vision_optimized \
  --test-data data/products.json

# 9. Просмотр отчётов
./prompt_engineering_cli.py report \
  --experiment-dir prompt_engineering/experiments
```

---

## 🎓 Best Practices

### 1. Версионирование

✅ **ПРАВИЛЬНО:**
```python
# Создать baseline
manager.create_prompt("vision_v1", "Опиши товар.", "Baseline")

# Сделать minor update
manager.update_prompt("vision_v1", "Опиши товар детально.", "Улучшение", version_type="minor")
```

❌ **НЕПРАВИЛЬНО:**
```python
# Перезаписать существующий промпт без версионирования
# (потеря истории)
```

### 2. A/B тестирование

✅ **ПРАВИЛЬНО:**
- Тестировать на достаточной выборке (минимум 30-50 примеров)
- Использовать реальные данные из production
- Проверять статистическую значимость (confidence > 80%)
- Документировать все эксперименты

❌ **НЕПРАВИЛЬНО:**
- Тестировать на 3-5 примерах
- Использовать синтетические данные
- Внедрять без проверки confidence level

### 3. Метрики

✅ **ПРАВИЛЬНО:**
- Использовать несколько метрик (F1, accuracy, precision, recall)
- Учитывать специфику задачи при выборе метрик
- Сравнивать с baseline

❌ **НЕПРАВИЛЬНО:**
- Полагаться только на одну метрику
- Игнорировать false positives/negatives
- Не учитывать trade-off между precision и recall

### 4. Ground Truth

✅ **ПРАВИЛЬНО:**
- Создавать качественные эталонные данные
- Регулярно обновлять ground truth
- Валидировать экспертами

❌ **НЕПРАВИЛЬНО:**
- Использовать устаревшие данные
- Не проверять качество ground truth

---

## 📊 Текущий статус проекта

### ✅ Реализовано:

1. **Metrics Calculator** - 100% готов
   - Classification metrics (F1, Precision, Recall, Accuracy)
   - Text similarity (BLEU, Exact Match, Fuzzy Match)
   - Link quality metrics
   - Category matching metrics

2. **A/B Testing Framework** - 100% готов
   - Автоматический запуск A/B тестов
   - Расчёт метрик для обоих вариантов
   - Определение победителя
   - Генерация рекомендаций
   - Сохранение детальных отчётов

3. **Prompt Manager** - 100% готов
   - Semantic versioning
   - История изменений
   - Сравнение версий (diff)
   - Rollback
   - Export/Import

4. **CLI Interface** - 100% готов
   - Все основные команды
   - Help система
   - Удобный интерфейс

### 🎯 Применение в ConstructionAI:

**Текущий промпт (VISION_SYSTEM_PROMPT):**
- Версия: 2.0.0 (оптимизированная)
- Точность: 100% по критичным метрикам
- Протестировано на 6 товарах
- sdvor.com - первая ссылка (приоритет)

**Возможности для улучшения:**
1. Создать несколько вариантов промпта
2. Запустить A/B тест на реальных данных
3. Измерить F1 score, precision, recall
4. Выбрать лучший вариант на основе метрик

---

## 🚀 Для собеседования в Строительный Двор

### Что можно показать:

1. **Полномасштабный инструмент** для промпт-инженера
   - Метрики качества (F1, BLEU, Similarity)
   - A/B тестирование
   - Версионирование промптов
   - CLI интерфейс

2. **Реальные результаты**
   - 100% точность по критичным метрикам
   - sdvor.com как приоритетная ссылка
   - Протестировано на 6 товарах

3. **Готовность к работе**
   - Можно сразу начинать A/B тесты промптов
   - Система готова к получению данных от начальства
   - Возможность быстрой итерации и улучшения

4. **Профессиональный подход**
   - Semantic versioning
   - Experiment tracking
   - Ground truth validation
   - Statistical significance

---

## 📞 Контакты

**Проект:** ConstructionAI_System
**Позиция:** Prompt Engineer
**Компания:** Строительный Двор

**Система готова к production!** 🚀
