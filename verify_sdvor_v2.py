import requests
import urllib.parse

def check_search(query):
    base_url = "https://sdvor.com/search" # Универсальная ссылка
    params = {'text': query}
    url = f"{base_url}?{urllib.parse.urlencode(params)}"
    print(f"Checking: {url}")
    
    headers = {
        'User-Agent': 'Mozilla/5.0'
    }
    
    try:
        r = requests.get(url, headers=headers, allow_redirects=False)
        print(f"Status: {r.status_code}")
        if 'location' in r.headers:
            print(f"Redirect: {r.headers['location']}")
    except Exception as e:
        print(f"Error: {e}")

check_search("Комплектующие")
check_search("Смеситель")
check_search("Ремкомплект")
