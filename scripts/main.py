import pandas as pd
import random
import sys
import time
from pathlib import Path

# Добавить корень проекта в path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.llm_client import GeminiClient
from src.prompts import ANALYST_SYSTEM_PROMPT, SUPPORT_AGENT_SYSTEM_PROMPT

# --- ЦВЕТА ДЛЯ ТЕРМИНАЛА ---
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

def print_banner():
    print(Colors.CYAN + Colors.BOLD)
    print("╔══════════════════════════════════════════╗")
    print("║       CONSTRUCTION AI SYSTEM v2.0        ║")
    print("║       Automated Customer Support         ║")
    print("╚══════════════════════════════════════════╝")
    print(Colors.ENDC)

def get_provider_choice():
    print(Colors.HEADER + "Select AI Provider:" + Colors.ENDC)
    print(f"1. {Colors.GREEN}Google Gemini Direct{Colors.ENDC} (Single Key)")
    print(f"2. {Colors.BLUE}OpenRouter Cloud{Colors.ENDC} (Multi-Key Rotation + Free Models)")
    
    while True:
        choice = input(f"\n{Colors.BOLD}Enter choice [1/2]: {Colors.ENDC}")
        if choice == "1":
            return "google"
        elif choice == "2":
            return "openrouter"
        else:
            print(Colors.FAIL + "Invalid choice. Try again." + Colors.ENDC)

def generate_fake_orders(count=5):
    products = ["цемент М500", "перфоратор Bosch", "ламинат дуб", "плитка Kerama"]
    complaints = ["привезли бой", "водитель хамил", "опоздали на 4 часа", "цвет не тот"]
    
    data = []
    for _ in range(count):
        if random.random() < 0.4: # 40% жалоб
            msg = f"Ужас! {random.choice(complaints)}! Заказ #{random.randint(1000,9999)}"
        else:
            msg = f"Здравствуйте, нужен {random.choice(products)}, доставка в Химки."
        data.append(msg)
    return data

def main():
    print_banner()
    provider = get_provider_choice()
    
    print(f"\n{Colors.BOLD}🚀 Initializing system with {provider.upper()}...{Colors.ENDC}")
    try:
        client = GeminiClient(provider=provider)
    except Exception as e:
        print(Colors.FAIL + f"Critical Error: {e}" + Colors.ENDC)
        return

    orders = generate_fake_orders(5)
    print(f"{Colors.CYAN}📦 Loaded {len(orders)} test cases.{Colors.ENDC}\n")
    
    results = []
    
    for i, msg in enumerate(orders):
        print(f"{Colors.BOLD}🔹 Case {i+1}:{Colors.ENDC} {msg}")
        
        # 1. ANALYST
        print(f"   Processing...", end="\r")
        analysis = client.generate_json(ANALYST_SYSTEM_PROMPT, msg)
        
        # Красивый вывод статуса
        intent = analysis.get("intent", "unknown")
        if intent == "complaint":
            status_color = Colors.FAIL
        elif intent == "sales":
            status_color = Colors.GREEN
        else:
            status_color = Colors.BLUE
            
        print(f"   📊 Intent: {status_color}{intent.upper()}{Colors.ENDC} | Urgency: {analysis.get('urgency')}")
        
        # 2. SUPPORT AGENT (Только для жалоб)
        reply = None
        if intent == "complaint":
            print(f"   {Colors.WARNING}🚨 Generating Apology Letter...{Colors.ENDC}")
            reply = client.generate(SUPPORT_AGENT_SYSTEM_PROMPT, msg)
            print(f"   ✅ Reply sent: \"{reply[:50]}...\"")
        else:
            print(f"   ✅ Routing to Sales Dept.")
            
        results.append({"msg": msg, "analysis": analysis, "reply": reply})
        print("-" * 40)
        time.sleep(0.5)

    # Save
    df = pd.DataFrame(results)
    df.to_csv("data/final_report.csv", index=False)
    print(f"\n{Colors.GREEN}✅ Done! Report saved to data/final_report.csv{Colors.ENDC}")

if __name__ == "__main__":
    main()