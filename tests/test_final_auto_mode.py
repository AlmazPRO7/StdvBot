#!/usr/bin/env python3
"""Финальный тест auto mode с vision"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.llm_client import GeminiClient
from src.prompts import VISION_SYSTEM_PROMPT
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
import base64

def create_test_image():
    """Создаёт изображение дрели"""
    img = Image.new('RGB', (400, 300), color='white')
    draw = ImageDraw.Draw(img)
    
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 30)
    except:
        font = None
    
    draw.rectangle([100, 80, 300, 220], fill='orange', outline='black', width=3)
    draw.text((150, 130), "ДРЕЛЬ", fill='black', font=font)
    draw.text((130, 170), "BOSCH", fill='blue', font=font)
    
    buffered = BytesIO()
    img.save(buffered, format="PNG")
    return buffered.getvalue()

def test_vision_auto():
    """Тест vision в auto режиме"""
    print("\n" + "="*70)
    print("🧪 ФИНАЛЬНЫЙ ТЕСТ AUTO MODE - VISION")
    print("="*70)
    
    client = GeminiClient()
    
    print(f"\n📊 Статус:")
    print(f"   Provider: {client.primary_provider}")
    print(f"   OpenRouter keys: {len(client.manager.keys)}")
    print(f"   Gemini Direct: {'✅ Available' if client.gemini_direct else '❌ Not available'}")
    
    if not client.gemini_direct:
        print("\n❌ Gemini Direct недоступен - fallback не будет работать!")
        return False
    
    print(f"\n🖼️ Создание тестового изображения...")
    image_bytes = create_test_image()
    
    print(f"⏳ Отправка vision запроса...")
    print("   (Ожидаем: OpenRouter 429 → Gemini fallback)")
    
    try:
        result = client.generate_with_image(
            VISION_SYSTEM_PROMPT,
            "Что на этой картинке? Дай ссылки для поиска.",
            image_bytes
        )
        
        print(f"\n✅ УСПЕХ!")
        print(f"\n📝 Ответ:")
        print("="*70)
        print(result[:500])
        print("="*70)
        
        # Проверка ссылок
        links_count = result.count('href=')
        print(f"\n🔗 Найдено ссылок: {links_count}")
        
        if links_count >= 4:
            print("✅ Все 4 альтернативные ссылки присутствуют!")
        else:
            print(f"⚠️ Недостаточно ссылок (ожидалось 4, найдено {links_count})")
        
        return True
        
    except Exception as e:
        print(f"\n❌ ОШИБКА: {e}")
        return False

if __name__ == "__main__":
    success = test_vision_auto()
    exit(0 if success else 1)
