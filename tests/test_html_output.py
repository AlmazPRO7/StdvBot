#!/usr/bin/env python3
"""
Тест проверки HTML output от Vision API
Проверяет что ответ содержит корректные HTML теги
"""

import os
import sys
from src.ai_client import ai_client
from src.prompts import VISION_SYSTEM_PROMPT


def test_html_tags(response_text: str) -> dict:
    """
    Проверяет наличие HTML тегов в ответе

    Returns:
        dict с результатами проверки
    """
    checks = {
        "has_bold_tags": "<b>" in response_text and "</b>" in response_text,
        "has_link_tags": "<a href=" in response_text and "</a>" in response_text,
        "has_italic_tags": "<i>" in response_text and "</i>" in response_text,
        "link_count": response_text.count("<a href="),
        "is_plain_text": not any([
            "<b>" in response_text,
            "<a href=" in response_text,
            "<i>" in response_text
        ])
    }

    # Проверить что есть минимум 4 ссылки (sdvor, yandex, google, avito)
    checks["has_all_links"] = checks["link_count"] >= 4

    # Итоговая оценка
    checks["is_valid_html"] = (
        checks["has_bold_tags"] and
        checks["has_link_tags"] and
        checks["has_italic_tags"] and
        checks["has_all_links"] and
        not checks["is_plain_text"]
    )

    return checks


def test_vision_html_output():
    """
    Тест HTML output Vision API на тестовом изображении
    """
    print("=" * 80)
    print("🧪 ТЕСТ HTML OUTPUT (VISION API)")
    print("=" * 80)

    # Найти тестовое изображение
    test_images = [
        "test_images/drill.jpg",
        "test_images/paint.jpg",
        "test_images/profnastil.jpg",
        "demo_images/product_sample.jpg"
    ]

    test_image = None
    for img_path in test_images:
        if os.path.exists(img_path):
            test_image = img_path
            break

    if not test_image:
        print("⚠️ Тестовые изображения не найдены")
        print("💡 Создайте папку test_images/ и добавьте изображение товара")
        print("   Или отправьте фото через Telegram бота для ручного теста")
        return

    print(f"\n📸 Тестовое изображение: {test_image}")

    # Загрузить изображение
    with open(test_image, "rb") as f:
        image_bytes = f.read()

    print("🤖 Отправка запроса Vision API...")

    try:
        # Вызвать Vision API
        response = ai_client.generate_with_image(
            VISION_SYSTEM_PROMPT,
            "",  # caption пустой
            image_bytes
        )

        print("\n" + "=" * 80)
        print("📄 ОТВЕТ ОТ AI:")
        print("=" * 80)
        print(response)
        print("=" * 80)

        # Проверить HTML теги
        print("\n🔍 ПРОВЕРКА HTML ТЕГОВ:")
        print("-" * 80)

        checks = test_html_tags(response)

        for check_name, result in checks.items():
            if check_name == "link_count":
                emoji = "✅" if result >= 4 else "❌"
                print(f"  {emoji} {check_name}: {result} (минимум 4)")
            elif check_name == "is_plain_text":
                emoji = "❌" if result else "✅"
                print(f"  {emoji} {check_name}: {result} (должен быть False)")
            elif check_name == "is_valid_html":
                emoji = "✅" if result else "❌"
                print(f"\n🎯 {emoji} {check_name.upper()}: {result}")
            else:
                emoji = "✅" if result else "❌"
                print(f"  {emoji} {check_name}: {result}")

        print("=" * 80)

        if checks["is_valid_html"]:
            print("\n✅ УСПЕХ! HTML output корректен на 100%")
            return True
        else:
            print("\n❌ ОШИБКА! HTML output НЕ корректен")
            print("\n💡 Возможные причины:")
            if checks["is_plain_text"]:
                print("  - AI возвращает plain text вместо HTML")
                print("  - Проверьте что промпт VISION_SYSTEM_PROMPT содержит требования HTML")
            if not checks["has_bold_tags"]:
                print("  - Отсутствуют теги <b></b> для названия товара")
            if not checks["has_link_tags"]:
                print("  - Отсутствуют теги <a href=\"\"></a> для ссылок")
            if not checks["has_italic_tags"]:
                print("  - Отсутствуют теги <i></i> для совета")
            if not checks["has_all_links"]:
                print(f"  - Недостаточно ссылок: {checks['link_count']} (нужно 4)")

            return False

    except Exception as e:
        print(f"\n❌ ОШИБКА при вызове Vision API: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("\n")
    success = test_vision_html_output()
    print("\n")

    if success:
        sys.exit(0)
    else:
        sys.exit(1)
