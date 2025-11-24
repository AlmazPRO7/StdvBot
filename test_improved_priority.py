#!/usr/bin/env python3
"""Тест нового приоритета: Gemini primary → OpenRouter fallback"""
import sys
import os
import time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '.'))

from src.llm_client import GeminiClient
from src.prompts import VISION_SYSTEM_PROMPT
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO

def create_drill_image():
    """Создаёт изображение дрели Bosch"""
    img = Image.new('RGB', (500, 400), color='white')
    draw = ImageDraw.Draw(img)
    
    try:
        font_big = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 40)
        font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 25)
    except:
        font_big = font_small = None
    
    # Корпус дрели
    draw.rectangle([120, 100, 380, 250], fill='#0066CC', outline='black', width=3)
    
    # Бренд
    draw.text((180, 130), "BOSCH", fill='white', font=font_big)
    
    # Модель  
    draw.text((160, 185), "GSR 12V-15", fill='yellow', font=font_small)
    
    # Характеристики
    draw.text((150, 270), "Дрель-шуруповёрт", fill='black', font=font_small)
    draw.text((180, 310), "12V Li-Ion", fill='#666666', font=font_small)
    
    buffered = BytesIO()
    img.save(buffered, format="PNG")
    return buffered.getvalue()

def test_priority_and_links():
    """Тест приоритета Gemini и точности поисковых ссылок"""
    print("\n" + "="*80)
    print("🧪 ТЕСТ: GEMINI PRIMARY + ТОЧНЫЕ ПОИСКОВЫЕ ССЫЛКИ")
    print("="*80)
    
    client = GeminiClient()  # auto mode
    
    print(f"\n📊 Конфигурация:")
    print(f"   Provider: {client.primary_provider}")
    print(f"   Gemini Direct: {'✅' if client.gemini_direct else '❌'}")
    
    print(f"\n🖼️ Создание тестового изображения (Дрель Bosch GSR 12V-15)...")
    image_bytes = create_drill_image()
    
    print(f"\n⏳ Отправка vision запроса...")
    print("   Ожидаем: Gemini сработает ПЕРВЫМ (быстро, ~1-2 сек)")
    
    start_time = time.time()
    
    try:
        result = client.generate_with_image(
            VISION_SYSTEM_PROMPT,
            "Что на картинке? Дай точные ссылки для поиска в Екатеринбурге.",
            image_bytes
        )
        
        elapsed = time.time() - start_time
        
        print(f"\n✅ УСПЕХ за {elapsed:.2f} секунд!")
        print(f"\n📝 Ответ:")
        print("="*80)
        print(result)
        print("="*80)
        
        # Анализ ссылок
        print(f"\n🔍 ПРОВЕРКА ТОЧНОСТИ ПОИСКОВЫХ ССЫЛОК:")
        print("="*80)
        
        checks = {
            "sdvor.com/ekb/search?text=Bosch": "✅ Точный поиск на sdvor.com (Бренд + Тип)" if "sdvor.com/ekb/search?text=Bosch" in result else "❌ Нет точного поиска sdvor.com",
            "market.yandex.ru/search?text=Bosch": "✅ Яндекс Маркет" if "market.yandex.ru/search?text=Bosch" in result or "market.yandex.ru/search?text=BOSCH" in result else "❌ Нет Яндекс Маркет",
            "&lr=54": "✅ Регион Екатеринбург (lr=54)" if "&lr=54" in result or "lr=54" in result else "❌ Нет региона ЕКБ",
            "google.com/search?q=": "✅ Google поиск" if "google.com/search?q=" in result else "❌ Нет Google",
            "Екатеринбург" in result or "екатеринбург" in result or "ЕКБ" in result: "✅ Упоминание Екатеринбурга" if ("Екатеринбург" in result or "екатеринбург" in result or "ЕКБ" in result) else "❌ Нет упоминания региона",
            "avito.ru/ekaterinburg": "✅ Avito с регионом ЕКБ" if "avito.ru/ekaterinburg" in result else "❌ Нет Avito ЕКБ",
        }
        
        for key, value in checks.items():
            if isinstance(key, bool):
                print(f"   {value}")
            else:
                print(f"   {value}")
        
        # Скорость
        print(f"\n⚡ ПРОИЗВОДИТЕЛЬНОСТЬ:")
        print("="*80)
        if elapsed < 3:
            print(f"   ✅ ОТЛИЧНО! {elapsed:.2f}с - Gemini Direct сработал первым!")
        elif elapsed < 20:
            print(f"   ⚠️ СРЕДНЕ: {elapsed:.2f}с - возможно был fallback на OpenRouter")
        else:
            print(f"   ❌ МЕДЛЕННО: {elapsed:.2f}с - проверьте логи")
        
        return True
        
    except Exception as e:
        print(f"\n❌ ОШИБКА: {e}")
        return False

if __name__ == "__main__":
    success = test_priority_and_links()
    exit(0 if success else 1)
