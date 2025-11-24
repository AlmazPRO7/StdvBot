import requests
import urllib.parse

def check_search(query):
    base_url = "https://sdvor.com/search"
    params = {'freeTextSearch': query}
    url = f"{base_url}?{urllib.parse.urlencode(params)}"
    print(f"Checking: {url}")
    
    try:
        r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, allow_redirects=False)
        print(f"Status: {r.status_code}")
        if 'location' in r.headers:
            print(f"Redirect: {r.headers['location']}")
    except Exception as e:
        print(f"Error: {e}")

print("--- TESTING freeTextSearch ---")
check_search("Кран-букса")
check_search("Вентиль")
check_search("Кран Masterprof")
