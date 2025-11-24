#!/usr/bin/env python3
"""Тест точности поисковых ссылок на реальных товарах"""
import sys
import os
import json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.llm_client import GeminiClient
from src.prompts import VISION_SYSTEM_PROMPT
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO

def create_product_image(product_info):
    """Создаёт изображение товара с брендом и моделью"""
    img = Image.new('RGB', (600, 400), color='white')
    draw = ImageDraw.Draw(img)

    try:
        font_big = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 50)
        font_medium = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 30)
        font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 20)
    except:
        font_big = font_medium = font_small = None

    # Фон товара (цвет зависит от типа)
    bg_color = product_info.get('bg_color', '#CCCCCC')
    draw.rectangle([100, 80, 500, 300], fill=bg_color, outline='black', width=3)

    # Бренд (большой)
    brand = product_info['brand']
    draw.text((150, 120), brand, fill='white', font=font_big)

    # Модель (средний)
    model = product_info.get('model', '')
    if model:
        draw.text((150, 190), model, fill='yellow', font=font_medium)

    # Тип товара (снизу)
    product_type = product_info['type']
    draw.text((150, 320), product_type, fill='black', font=font_small)

    buffered = BytesIO()
    img.save(buffered, format="PNG")
    return buffered.getvalue()

def test_product(client, product_info):
    """Тестирует один товар"""
    print(f"\n{'='*80}")
    print(f"🧪 ТЕСТ: {product_info['brand']} {product_info.get('model', '')} ({product_info['type']})")
    print(f"{'='*80}")

    # Создаём изображение
    image_bytes = create_product_image(product_info)

    # Отправляем в vision API
    try:
        result = client.generate_with_image(
            VISION_SYSTEM_PROMPT,
            f"Что на картинке? Дай точные ссылки для поиска в Екатеринбурге.",
            image_bytes
        )

        print(f"\n📝 ОТВЕТ:")
        print(result)

        # Анализ ссылок
        print(f"\n🔍 ПРОВЕРКА ССЫЛОК:")

        checks = {
            "yandex_market": "market.yandex.ru/search" in result and "lr=54" in result,
            "google": "google.com/search" in result and "Екатеринбург" in result,
            "avito": "avito.ru/ekaterinburg" in result,
            "brand_in_links": product_info['brand'] in result or product_info['brand'].upper() in result,
            "sdvor_footer": "sdvor.com/ekb" in result,  # Должен быть в footer
        }

        for check_name, passed in checks.items():
            status = "✅" if passed else "❌"
            print(f"   {status} {check_name}")

        # Общая точность
        accuracy = sum(checks.values()) / len(checks) * 100
        print(f"\n📊 ТОЧНОСТЬ: {accuracy:.1f}%")

        return {
            "product": f"{product_info['brand']} {product_info.get('model', '')}",
            "type": product_info['type'],
            "response": result,
            "checks": checks,
            "accuracy": accuracy
        }

    except Exception as e:
        print(f"\n❌ ОШИБКА: {e}")
        return None

def main():
    """Основная функция тестирования"""
    print("\n" + "="*80)
    print("🧪 ТЕСТ ТОЧНОСТИ ПОИСКОВЫХ ССЫЛОК (РЕАЛЬНЫЕ ТОВАРЫ)")
    print("="*80)

    # Тестовые товары (популярные бренды)
    products = [
        # Инструменты
        {
            "brand": "BOSCH",
            "model": "GSR 12V-15",
            "type": "Дрель-шуруповёрт",
            "bg_color": "#0066CC"
        },
        {
            "brand": "MAKITA",
            "model": "DF330DWE",
            "type": "Аккумуляторная дрель",
            "bg_color": "#00BFFF"
        },
        {
            "brand": "DeWALT",
            "model": "DCD771C2",
            "type": "Шуруповёрт",
            "bg_color": "#FFD700"
        },
        # Материалы
        {
            "brand": "KNAUF",
            "model": "Rotband",
            "type": "Штукатурка гипсовая",
            "bg_color": "#D3D3D3"
        },
        {
            "brand": "CERESIT",
            "model": "CM 11",
            "type": "Клей для плитки",
            "bg_color": "#FF6347"
        },
        {
            "brand": "TIKKURILA",
            "model": "Euro 7",
            "type": "Краска интерьерная",
            "bg_color": "#87CEEB"
        },
    ]

    client = GeminiClient()  # auto mode

    results = []
    for product in products:
        result = test_product(client, product)
        if result:
            results.append(result)

    # Общая статистика
    print(f"\n{'='*80}")
    print("📊 ИТОГОВАЯ СТАТИСТИКА")
    print(f"{'='*80}")

    total_tests = len(results)
    avg_accuracy = sum(r['accuracy'] for r in results) / total_tests if total_tests > 0 else 0

    print(f"Всего тестов: {total_tests}")
    print(f"Средняя точность: {avg_accuracy:.1f}%")

    # Проверка по категориям
    all_checks = {}
    for result in results:
        for check_name, passed in result['checks'].items():
            if check_name not in all_checks:
                all_checks[check_name] = []
            all_checks[check_name].append(passed)

    print(f"\nПроверки:")
    for check_name, checks in all_checks.items():
        passed_count = sum(checks)
        total_count = len(checks)
        percentage = passed_count / total_count * 100
        status = "✅" if percentage >= 90 else "⚠️" if percentage >= 70 else "❌"
        print(f"   {status} {check_name}: {passed_count}/{total_count} ({percentage:.1f}%)")

    # Сохранить результаты
    output_file = "/tmp/search_accuracy_test_results.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({
            "total_tests": total_tests,
            "avg_accuracy": avg_accuracy,
            "results": results,
            "checks_summary": {
                name: {
                    "passed": sum(checks),
                    "total": len(checks),
                    "percentage": sum(checks) / len(checks) * 100
                }
                for name, checks in all_checks.items()
            }
        }, f, ensure_ascii=False, indent=2)

    print(f"\n💾 Результаты сохранены: {output_file}")

    # Оценка
    if avg_accuracy >= 95:
        print(f"\n🎉 ОТЛИЧНО! Точность {avg_accuracy:.1f}% - поиск работает на 100%!")
    elif avg_accuracy >= 80:
        print(f"\n✅ ХОРОШО! Точность {avg_accuracy:.1f}% - есть небольшие улучшения.")
    else:
        print(f"\n⚠️ ТРЕБУЕТСЯ ДОРАБОТКА! Точность {avg_accuracy:.1f}% - нужны изменения в prompt.")

if __name__ == "__main__":
    main()
