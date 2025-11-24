import sys
import time
from src.llm_client import GeminiClient
from src.prompts import ANALYST_SYSTEM_PROMPT, SUPPORT_AGENT_SYSTEM_PROMPT

class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

def typing_effect(text):
    """Эффект печатающей машинки"""
    for char in text:
        sys.stdout.write(char)
        sys.stdout.flush()
        time.sleep(0.01)
    print()

def main():
    print(Colors.HEADER + Colors.BOLD)
    print("╔═════════════════════════════════════════════╗")
    print("║   CONSTRUCTION AI: LIVE INTERACTIVE DEMO    ║")
    print("╚═════════════════════════════════════════════╝")
    print(Colors.ENDC)
    
    print("Initializing Neural Core...", end="\r")
    try:
        # По умолчанию пробуем OpenRouter, он сам переключится на Google если что
        client = GeminiClient(provider="openrouter") 
        print(f"{Colors.GREEN}✔ SYSTEM ONLINE{Colors.ENDC} (Provider: {client.primary_provider.upper()} + Failover)")
    except Exception as e:
        print(f"{Colors.FAIL}❌ SYSTEM FAILURE: {e}{Colors.ENDC}")
        return

    print("\nType a message as a customer (or 'exit' to quit).\n")

    while True:
        try:
            user_input = input(f"{Colors.BOLD}Customer:{Colors.ENDC} ")
            if user_input.lower() in ['exit', 'quit', 'q']:
                print("Shutting down...")
                break
            
            if not user_input.strip():
                continue

            # 1. ANALYST NODE
            print(f"\n{Colors.CYAN}⚡ AI Analyst thinking...{Colors.ENDC}", end="\r")
            start_time = time.time()
            analysis = client.generate_json(ANALYST_SYSTEM_PROMPT, user_input)
            duration = time.time() - start_time
            
            # Красивый вывод JSON
            intent = analysis.get("intent", "unknown").upper()
            sentiment = analysis.get("sentiment", "unknown")
            urgency = analysis.get("urgency", "low")
            
            # Цвет статуса
            if intent == "COMPLAINT": color = Colors.FAIL
            elif intent == "SALES": color = Colors.GREEN
            else: color = Colors.BLUE
            
            print(" " * 50, end="\r") # Очистка строки
            print(f"🔍 {Colors.BOLD}CLASSIFICATION ({duration:.1f}s):{Colors.ENDC}")
            print(f"   Intent:    {color}{intent}{Colors.ENDC}")
            print(f"   Sentiment: {sentiment}")
            print(f"   Urgency:   {urgency}")
            print(f"   Summary:   {analysis.get('summary')}")

            # 2. SUPPORT NODE (Если нужно)
            if intent == "COMPLAINT" or sentiment == "negative":
                print(f"\n{Colors.WARNING}🚨 NEGATIVE SENTIMENT DETECTED. Engaged Support Agent.{Colors.ENDC}")
                print(f"{Colors.CYAN}✍️  Drafting response...{Colors.ENDC}", end="\r")
                
                reply = client.generate(SUPPORT_AGENT_SYSTEM_PROMPT, user_input)
                
                print(" " * 50, end="\r")
                print(f"{Colors.BOLD}🤖 AI AGENT REPLY:{Colors.ENDC}")
                print(Colors.CYAN + "-"*40 + Colors.ENDC)
                typing_effect(reply.strip())
                print(Colors.CYAN + "-"*40 + Colors.ENDC)
            
            print("\n")

        except KeyboardInterrupt:
            print("\nGoodbye!")
            break
        except Exception as e:
            print(f"\n{Colors.FAIL}Error: {e}{Colors.ENDC}\n")

if __name__ == "__main__":
    main()
