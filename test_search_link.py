import asyncio
import logging
from src.llm_client import GeminiClient
from src.prompts import VISION_SYSTEM_PROMPT

# Mock Gemini Client to see what prompts do
async def test_generation():
    client = GeminiClient()
    
    # Симулируем запрос с фото кран-буксы (текстом, так как это vision prompt)
    # Мы просим модель "представить", что она видит кран-буксу
    user_text = "На фото изображена Кран-букса 1/2 дюйма Masterprof"
    
    print("--- TESTING PROMPT GENERATION ---")
    response = client.generate(VISION_SYSTEM_PROMPT, user_text)
    
    print("\n--- AI RESPONSE ---")
    print(response)
    
    if "sdvor.com" in response:
        import re
        link_match = re.search(r'href="(https://sdvor.com/ekb/search\?text=.*?)"', response)
        if link_match:
            print(f"\n✅ Generated Link: {link_match.group(1)}")
        else:
            print("\n❌ Link format mismatch")
    else:
        print("\n❌ No sdvor link found")

if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    loop.run_until_complete(test_generation())
