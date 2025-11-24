#!/usr/bin/env python3
"""
Тестирование прямого Google Gemini API с vision (через OAuth ADC)
"""
import requests
import json
import base64
import time
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont

# Импортируем google-auth для OAuth
try:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    import google.auth
except ImportError:
    print("❌ Установите google-auth: pip install google-auth google-auth-oauthlib")
    exit(1)

# Google Gemini API endpoint
GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"
MODEL = "gemini-2.0-flash-exp"

def get_access_token():
    """Получает access token через Application Default Credentials"""
    try:
        # Используем ADC (Application Default Credentials)
        credentials, project = google.auth.default(
            scopes=['https://www.googleapis.com/auth/generative-language.retriever']
        )

        # Обновляем токен если нужно
        if not credentials.valid:
            if credentials.expired and credentials.refresh_token:
                credentials.refresh(Request())

        return credentials.token
    except Exception as e:
        print(f"❌ Ошибка получения токена: {e}")
        return None

def create_test_image():
    """Создаёт простое тестовое изображение"""
    img = Image.new('RGB', (400, 300), color='blue')
    draw = ImageDraw.Draw(img)

    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 40)
    except:
        font = ImageFont.load_default()

    draw.text((80, 120), "GEMINI TEST", fill='white', font=font)

    # Конвертируем в base64
    buffer = BytesIO()
    img.save(buffer, format='JPEG')
    return base64.b64encode(buffer.getvalue()).decode('utf-8')

def test_gemini_vision(access_token):
    """Тестирует Gemini API с vision запросом"""
    print(f"\n{'='*70}")
    print(f"🚀 ТЕСТИРОВАНИЕ GOOGLE GEMINI API (ПРЯМОЙ ДОСТУП)")
    print(f"{'='*70}")
    print(f"📦 Модель: {MODEL}")
    print(f"🔐 OAuth: Application Default Credentials")

    # Создаём тестовое изображение
    base64_image = create_test_image()

    # URL для запроса
    url = f"{GEMINI_API_BASE}/{MODEL}:generateContent"

    # Headers с OAuth токеном
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    # Payload для Gemini API (формат отличается от OpenRouter!)
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": "Что изображено на этой картинке? Опиши цвет фона и текст."},
                    {
                        "inline_data": {
                            "mime_type": "image/jpeg",
                            "data": base64_image
                        }
                    }
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.3,
            "maxOutputTokens": 100
        }
    }

    # Делаем запрос
    try:
        print(f"\n📡 Отправка запроса...")
        start_time = time.time()
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        elapsed = time.time() - start_time

        print(f"📊 HTTP Status: {response.status_code}")
        print(f"⏱️  Response Time: {elapsed:.2f}s")

        if response.status_code == 200:
            data = response.json()

            # Парсим ответ (формат Gemini API)
            if 'candidates' in data and len(data['candidates']) > 0:
                content = data['candidates'][0]['content']['parts'][0]['text']
                print(f"✅ УСПЕХ!")
                print(f"📝 Ответ модели:\n{content}")

                # Показываем usage metadata
                if 'usageMetadata' in data:
                    usage = data['usageMetadata']
                    print(f"\n📊 Tokens:")
                    print(f"   Prompt: {usage.get('promptTokenCount', 0)}")
                    print(f"   Response: {usage.get('candidatesTokenCount', 0)}")
                    print(f"   Total: {usage.get('totalTokenCount', 0)}")

                return True
            else:
                print(f"⚠️  Некорректный формат ответа:")
                print(json.dumps(data, indent=2, ensure_ascii=False)[:500])
                return False

        elif response.status_code == 429:
            print(f"⚠️  RATE LIMIT (429)")
            print(f"💡 Ответ API: {response.text[:300]}")
            return False

        elif response.status_code == 401:
            print(f"❌ ОШИБКА АВТОРИЗАЦИИ (401)")
            print(f"💡 Токен недействителен или истёк")
            print(f"💡 Ответ API: {response.text[:300]}")
            return False

        elif response.status_code == 403:
            print(f"❌ ДОСТУП ЗАПРЕЩЁН (403)")
            print(f"💡 Возможно API не активирован для проекта")
            print(f"💡 Ответ API: {response.text[:300]}")
            return False

        else:
            print(f"❌ ОШИБКА {response.status_code}")
            print(f"💡 Ответ API: {response.text[:500]}")
            return False

    except requests.exceptions.Timeout:
        print(f"⏰ TIMEOUT - запрос превысил 30 секунд")
        return False

    except Exception as e:
        print(f"❌ EXCEPTION: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_gemini_text_only(access_token):
    """Тестирует Gemini API с обычным текстовым запросом"""
    print(f"\n{'='*70}")
    print(f"📝 ТЕСТИРОВАНИЕ ТЕКСТОВОГО ЗАПРОСА (БЕЗ VISION)")
    print(f"{'='*70}")

    url = f"{GEMINI_API_BASE}/{MODEL}:generateContent"

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    payload = {
        "contents": [
            {
                "parts": [
                    {"text": "Напиши одно предложение про искусственный интеллект."}
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.5,
            "maxOutputTokens": 50
        }
    }

    try:
        print(f"📡 Отправка запроса...")
        start_time = time.time()
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        elapsed = time.time() - start_time

        print(f"📊 HTTP Status: {response.status_code}")
        print(f"⏱️  Response Time: {elapsed:.2f}s")

        if response.status_code == 200:
            data = response.json()
            content = data['candidates'][0]['content']['parts'][0]['text']
            print(f"✅ УСПЕХ!")
            print(f"📝 Ответ: {content}")

            if 'usageMetadata' in data:
                usage = data['usageMetadata']
                print(f"📊 Tokens: {usage.get('totalTokenCount', 0)}")

            return True
        else:
            print(f"❌ ОШИБКА {response.status_code}: {response.text[:300]}")
            return False

    except Exception as e:
        print(f"❌ EXCEPTION: {e}")
        return False

def main():
    """Главная функция"""
    print("\n" + "="*70)
    print("🔐 ПОЛУЧЕНИЕ OAUTH ТОКЕНА")
    print("="*70)

    access_token = get_access_token()

    if not access_token:
        print("\n❌ Не удалось получить access token!")
        print("💡 Проверьте:")
        print("   1. ADC настроены: ls ~/.config/gcloud/application_default_credentials.json")
        print("   2. Учётная запись активна: gcloud auth application-default login")
        return False

    print(f"✅ Access token получен: ...{access_token[-20:]}")

    # Тест 1: Текстовый запрос
    text_ok = test_gemini_text_only(access_token)

    # Тест 2: Vision запрос
    vision_ok = test_gemini_vision(access_token)

    # Итоги
    print(f"\n{'='*70}")
    print(f"📊 ИТОГИ ТЕСТИРОВАНИЯ")
    print(f"{'='*70}")
    print(f"{'✅' if text_ok else '❌'} Текстовый запрос: {'РАБОТАЕТ' if text_ok else 'НЕ РАБОТАЕТ'}")
    print(f"{'✅' if vision_ok else '❌'} Vision запрос: {'РАБОТАЕТ' if vision_ok else 'НЕ РАБОТАЕТ'}")
    print(f"{'='*70}\n")

    if text_ok or vision_ok:
        print("🎉 Google Gemini API работает!")
        print("💡 Можно использовать как альтернативу OpenRouter")
        print("💰 Бесплатный tier: 1500 запросов/день")

    return text_ok or vision_ok

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
