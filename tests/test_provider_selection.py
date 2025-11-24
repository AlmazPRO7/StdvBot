#!/usr/bin/env python3
"""
Тест выбора провайдера: openrouter, gemini, auto
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.llm_client import GeminiClient

def test_provider(provider_name):
    """Тестирует конкретного провайдера"""
    print(f"\n{'='*70}")
    print(f"🧪 ТЕСТ ПРОВАЙДЕРА: {provider_name.upper()}")
    print(f"{'='*70}")

    client = GeminiClient(provider=provider_name)

    system_prompt = "Ты помощник. Отвечай кратко."
    user_text = "Напиши одно предложение про выбор провайдера AI."

    print(f"📡 Отправка запроса...")
    print(f"   Provider: {client.primary_provider}")

    try:
        result = client.generate(system_prompt, user_text, temperature=0.5)
        print(f"\n✅ УСПЕХ!")
        print(f"📝 Ответ: {result[:100]}...")
        return True
    except Exception as e:
        print(f"\n❌ ОШИБКА: {e}")
        return False

def main():
    """Тест всех трёх вариантов"""
    print("\n" + "="*70)
    print("🚀 ТЕСТИРОВАНИЕ ВЫБОРА AI ПРОВАЙДЕРА")
    print("="*70)

    results = {}

    # Тест 1: OpenRouter (только)
    print("\n📌 OpenRouter исчерпан (429) - ожидается Error или быстрый fail")
    results["openrouter"] = test_provider("openrouter")

    # Тест 2: Gemini Direct (приоритет)
    print("\n📌 Gemini Direct - ожидается немедленный успех")
    results["gemini"] = test_provider("gemini")

    # Тест 3: Auto (fallback)
    print("\n📌 Auto mode - ожидается OpenRouter → Gemini fallback")
    results["auto"] = test_provider("auto")

    # Итоги
    print(f"\n{'='*70}")
    print("📊 ИТОГИ ТЕСТИРОВАНИЯ")
    print(f"{'='*70}")

    for provider, success in results.items():
        emoji = "✅" if success else "❌"
        status = "PASSED" if success else "FAILED"
        print(f"{emoji} {provider.upper()}: {status}")

    print(f"\n{'='*70}")
    print("💡 РЕКОМЕНДАЦИИ:")
    print(f"{'='*70}")
    print("1. AI_PROVIDER=openrouter → Только OpenRouter (может fail при 429)")
    print("2. AI_PROVIDER=gemini     → Только Gemini (быстро, но нет fallback)")
    print("3. AI_PROVIDER=auto       → Умный fallback (РЕКОМЕНДУЕТСЯ)")
    print()
    print("📝 Установить в .env:")
    print("   AI_PROVIDER=auto  # для production")
    print("   AI_PROVIDER=gemini  # для экономии OpenRouter квоты")
    print(f"{'='*70}\n")

    return all(results.values())

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
