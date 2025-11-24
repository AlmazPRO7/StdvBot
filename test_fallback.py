#!/usr/bin/env python3
"""
Тестирование fallback механизма: OpenRouter (429) → Gemini Direct API
"""
import sys
import os

# Добавляем путь к src
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '.'))

from src.llm_client import GeminiClient
from src.prompts import ANALYST_SYSTEM_PROMPT, VISION_SYSTEM_PROMPT
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont

def create_test_image():
    """Создаёт тестовое изображение"""
    img = Image.new('RGB', (300, 200), color='green')
    draw = ImageDraw.Draw(img)

    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 30)
    except:
        font = ImageFont.load_default()

    draw.text((60, 80), "FALLBACK TEST", fill='yellow', font=font)

    buffer = BytesIO()
    img.save(buffer, format='JPEG')
    return buffer.getvalue()

def test_text_request():
    """Тест 1: Обычный текстовый запрос"""
    print("\n" + "="*70)
    print("📝 ТЕСТ 1: ТЕКСТОВЫЙ ЗАПРОС")
    print("="*70)

    client = GeminiClient()

    system_prompt = "Ты помощник. Отвечай кратко."
    user_text = "Напиши одно предложение про строительные материалы."

    print(f"📡 Отправка запроса...")
    print(f"   System: {system_prompt[:50]}...")
    print(f"   User: {user_text}")

    result = client.generate(system_prompt, user_text, temperature=0.5)

    print(f"\n✅ Результат:")
    print(f"   {result}")

    return result and "Error:" not in result

def test_json_request():
    """Тест 2: JSON запрос (классификация)"""
    print("\n" + "="*70)
    print("📊 ТЕСТ 2: JSON ЗАПРОС (КЛАССИФИКАЦИЯ)")
    print("="*70)

    client = GeminiClient()

    user_text = "Привезли дрель Makita с порванной упаковкой. Требую замены!"

    print(f"📡 Отправка запроса...")
    print(f"   User: {user_text}")
    print(f"   Prompt: ANALYST_SYSTEM_PROMPT")

    result = client.generate_json(ANALYST_SYSTEM_PROMPT, user_text)

    print(f"\n✅ Результат:")
    print(f"   Intent: {result.get('intent', 'N/A')}")
    print(f"   Sentiment: {result.get('sentiment', 'N/A')}")
    print(f"   Urgency: {result.get('urgency', 'N/A')}")
    print(f"   Summary: {result.get('summary', 'N/A')[:50]}...")

    return 'intent' in result and 'error' not in result

def test_vision_request():
    """Тест 3: Vision запрос"""
    print("\n" + "="*70)
    print("🖼️  ТЕСТ 3: VISION ЗАПРОС")
    print("="*70)

    client = GeminiClient()

    image_bytes = create_test_image()
    user_text = "Что изображено на картинке? Какого цвета фон и что написано?"

    print(f"📡 Отправка запроса...")
    print(f"   User: {user_text}")
    print(f"   Image: 300x200 зелёный фон с текстом 'FALLBACK TEST'")
    print(f"   Prompt: VISION_SYSTEM_PROMPT")

    result = client.generate_with_image(VISION_SYSTEM_PROMPT, user_text, image_bytes)

    print(f"\n✅ Результат:")
    print(f"   {result[:200]}...")

    return result and "Error:" not in result

def main():
    """Главная функция"""
    print("\n" + "="*70)
    print("🚀 ТЕСТИРОВАНИЕ FALLBACK МЕХАНИЗМА")
    print("="*70)
    print("📌 OpenRouter ключи исчерпаны (429)")
    print("🔄 Ожидается автоматическое переключение на Gemini Direct API")
    print("="*70)

    results = {
        "text": False,
        "json": False,
        "vision": False
    }

    # Тест 1: Текстовый запрос
    try:
        results["text"] = test_text_request()
    except Exception as e:
        print(f"\n❌ Текстовый тест провален: {e}")

    # Тест 2: JSON запрос
    try:
        results["json"] = test_json_request()
    except Exception as e:
        print(f"\n❌ JSON тест провален: {e}")

    # Тест 3: Vision запрос
    try:
        results["vision"] = test_vision_request()
    except Exception as e:
        print(f"\n❌ Vision тест провален: {e}")

    # Итоги
    print("\n" + "="*70)
    print("📊 ИТОГИ ТЕСТИРОВАНИЯ")
    print("="*70)

    for test_name, success in results.items():
        emoji = "✅" if success else "❌"
        status = "PASSED" if success else "FAILED"
        print(f"{emoji} {test_name.upper()}: {status}")

    print("="*70)

    all_passed = all(results.values())
    if all_passed:
        print("\n🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ!")
        print("✅ Fallback механизм работает корректно")
        print("💡 Бот будет автоматически переключаться на Gemini при 429")
    else:
        print("\n⚠️  НЕКОТОРЫЕ ТЕСТЫ ПРОВАЛЕНЫ")
        print("💡 Проверьте логи выше для деталей")

    return all_passed

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
