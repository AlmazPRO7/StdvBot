#!/usr/bin/env python3
"""
Тест улучшенного Vision промпта (с альтернативными ссылками)
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '.'))

from src.llm_client import GeminiClient
from src.prompts import VISION_SYSTEM_PROMPT
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont

def create_baofeng_radio_image():
    """Создаёт изображение рации Baofeng UV-5R"""
    img = Image.new('RGB', (400, 500), color='black')
    draw = ImageDraw.Draw(img)

    try:
        font_large = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 40)
        font_medium = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 25)
    except:
        font_large = ImageFont.load_default()
        font_medium = ImageFont.load_default()

    # Рисуем "корпус рации"
    draw.rectangle([(80, 50), (320, 450)], fill='darkgreen', outline='gray', width=3)

    # Дисплей
    draw.rectangle([(100, 80), (300, 150)], fill='darkblue', outline='lightblue', width=2)

    # Текст на дисплее
    draw.text((110, 90), "BAOFENG", fill='lightgreen', font=font_medium)
    draw.text((110, 120), "UV-5R", fill='yellow', font=font_large)

    # Кнопки
    for y in range(200, 400, 50):
        draw.rectangle([(120, y), (280, y+30)], fill='gray', outline='white', width=1)

    # Антенна
    draw.rectangle([(190, 20), (210, 50)], fill='silver')

    buffer = BytesIO()
    img.save(buffer, format='JPEG')
    return buffer.getvalue()

def test_vision_with_improved_prompt():
    """Тест Vision с улучшенным промптом"""
    print("\n" + "="*70)
    print("🖼️  ТЕСТ УЛУЧШЕННОГО VISION ПРОМПТА")
    print("="*70)
    print("📦 Товар: Рация Baofeng UV-5R (НЕТ на sdvor.com)")
    print("🔗 Ожидаем: Ссылки на Яндекс Маркет, Google, Авито")
    print("="*70)

    client = GeminiClient()
    image_bytes = create_baofeng_radio_image()

    user_text = "Что это за устройство? Где можно купить?"

    print(f"\n📡 Отправка запроса через Gemini API...")
    print(f"   Изображение: 400x500 (чёрный фон, зелёная рация с текстом BAOFENG UV-5R)")

    result = client.generate_with_image(VISION_SYSTEM_PROMPT, user_text, image_bytes)

    print(f"\n✅ РЕЗУЛЬТАТ:")
    print("="*70)
    print(result)
    print("="*70)

    # Проверяем что в ответе есть нужные ссылки
    checks = {
        "Яндекс Маркет": "market.yandex.ru" in result,
        "Google общий": "google.com/search?q=" in result and "site:" not in result,
        "Авито": "avito.ru" in result,
        "Предупреждение": "Если товара нет" in result or "используйте" in result,
        "Категория на сайте": "sdvor.com" in result
    }

    print(f"\n📊 ПРОВЕРКА ССЫЛОК:")
    print("="*70)
    for check_name, passed in checks.items():
        emoji = "✅" if passed else "❌"
        print(f"{emoji} {check_name}: {'Есть' if passed else 'Отсутствует'}")

    all_passed = all(checks.values())

    print(f"\n{'='*70}")
    if all_passed:
        print("🎉 ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ!")
        print("✅ Теперь пользователь ВСЕГДА найдёт товар (даже если нет на sdvor.com)")
    else:
        print("⚠️  НЕКОТОРЫЕ ПРОВЕРКИ ПРОВАЛЕНЫ")
        print("💡 Возможно нужно улучшить промпт")

    return all_passed

if __name__ == "__main__":
    success = test_vision_with_improved_prompt()
    exit(0 if success else 1)
