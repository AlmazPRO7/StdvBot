import requests
import urllib.parse

def check_search(query):
    base_url = "https://www.sdvor.com/ekb/search"
    params = {'text': query}
    url = f"{base_url}?{urllib.parse.urlencode(params)}"
    print(f"Checking: {url}")
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    try:
        # SDVOR redirects to captcha often, but let's see the initial code
        r = requests.get(url, headers=headers, allow_redirects=False)
        print(f"Status: {r.status_code}")
        if 'location' in r.headers:
            print(f"Redirect: {r.headers['location']}")
        
        # If it's 302 to showcaptcha, the URL is theoretically valid format-wise.
        # But we can't know if it found products without solving captcha.
    except Exception as e:
        print(f"Error: {e}")

print("--- TEST 1: Space vs Plus ---")
check_search("Кран Masterprof") # uses + by default in urlencode
# check_search("Кран%20Masterprof") # manual handling needed for %20 if library doesn't do it

print("\n--- TEST 2: Brand vs No Brand ---")
check_search("Кран")
check_search("Вентиль")
