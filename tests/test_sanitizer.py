import re
import urllib.parse
import logging

# Copy-paste of the function from telegram_bot.py to test isolation
def sanitize_sdvor_links(text):
    def replacer(match):
        original_url = match.group(0)
        query_param = match.group(1)
        
        print(f"Found query: {query_param}")
        
        try:
            # Simulate decoding
            decoded = urllib.parse.unquote_plus(query_param).strip()
            print(f"Decoded: {decoded}")
            
            words = decoded.split()
            if not words: return original_url
            
            first_word = words[0].lower()
            print(f"First word (lower): {first_word}")
            
            risky_keywords = [
                "кран", "букса", "вентиль", "саморез", "саморезы", 
                "дюбель", "муфта", "фитинг", "гайка", "болт", "шайба",
                "уголок", "тройник", "заглушка", "хомут", "прокладка", "пена"
            ]
            
            if any(first_word.startswith(k) for k in risky_keywords):
                # Capitalize first letter for aesthetics, keep the rest lowercase
                clean_word = words[0].capitalize()
                new_query = urllib.parse.quote_plus(clean_word)
                print(f"SANITIZED -> {clean_word} ({new_query})")
                return f'href="https://sdvor.com/ekb/search?text={new_query}"'
            
            print("Not risky, keeping original.")
            return original_url
            
        except Exception as e:
            print(f"Error: {e}")
            return original_url

    pattern = r'href="https://(?:www\.)?sdvor\.com/ekb/search\?text=([^"]+)"'
    return re.sub(pattern, replacer, text)

# Test Cases
test_1 = 'Link: <a href="https://sdvor.com/ekb/search?text=Кран+Masterprof">'
test_2 = 'Link: <a href="https://sdvor.com/ekb/search?text=%D0%9A%D1%80%D0%B0%D0%BD+%D0%91%D1%83%D0%BA%D1%81%D0%B0">'
test_3 = 'Link: <a href="https://sdvor.com/ekb/search?text=Дрель+Makita">'

print("--- TEST 1 (Кран Masterprof) ---")
print(sanitize_sdvor_links(test_1))

print("\n--- TEST 2 (Кран Букса Encoded) ---")
print(sanitize_sdvor_links(test_2))

print("\n--- TEST 3 (Дрель Makita) ---")
print(sanitize_sdvor_links(test_3))
