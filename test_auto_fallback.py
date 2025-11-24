#!/usr/bin/env python3
"""Тест auto mode с fallback на Gemini"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '.'))

from src.llm_client import GeminiClient
from src.prompts import ANALYST_SYSTEM_PROMPT

def test_auto_fallback():
    """Тест режима auto - должен переключиться на Gemini при 429"""
    print("\n" + "="*70)
    print("🧪 ТЕСТ AUTO MODE С FALLBACK")
    print("="*70)
    
    client = GeminiClient()  # По умолчанию из Config (auto)
    
    print(f"\n📡 Provider: {client.primary_provider}")
    print(f"🔑 OpenRouter keys: {len(client.manager.keys)}")
    print(f"✅ Gemini Direct: {'Available' if client.gemini_direct else 'Not available'}")
    
    print(f"\n⏳ Отправка запроса...")
    print("   (Ожидаем: OpenRouter 429 → Gemini fallback)")
    
    try:
        result = client.generate(
            ANALYST_SYSTEM_PROMPT,
            "Напиши одно предложение про автоматический fallback.",
            temperature=0.5
        )
        
        print(f"\n✅ УСПЕХ!")
        print(f"📝 Ответ: {result[:150]}...")
        return True
        
    except Exception as e:
        print(f"\n❌ ОШИБКА: {e}")
        return False

if __name__ == "__main__":
    success = test_auto_fallback()
    exit(0 if success else 1)
