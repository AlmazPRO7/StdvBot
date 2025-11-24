import pandas as pd
import os
import random

# Создаем папку для демо-данных
os.makedirs("data/demo", exist_ok=True)

# --- 1. Смешанный файл (Идеальный для графиков) ---
mixed_data = []
intents = ["sales", "complaint", "question", "spam"]
products = ["цемент", "ламинат", "дрель", "гвозди"]

for _ in range(30):
    intent = random.choice(intents)
    if intent == "sales":
        msg = f"Куплю {random.choice(products)}, 50 штук."
    elif intent == "complaint":
        msg = f"Почему {random.choice(products)} приехал сломанный?! Верните деньги!"
    elif intent == "question":
        msg = f"А {random.choice(products)} есть в наличии на складе?"
    else:
        msg = "Предлагаем продвижение сайта, недорого."
    
    mixed_data.append(msg)

pd.DataFrame(mixed_data, columns=["message"]).to_csv("data/demo/1_mixed_requests.csv", index=False)
print("✅ Created data/demo/1_mixed_requests.csv")

# --- 2. Чистый негатив (Для проверки массовых извинений) ---
angry_data = [
    "Вы что там, уснули? Где доставка?",
    "Товар бракованный, упаковка рваная.",
    "Курьер нахамил жене, я буду жаловаться в суд!",
    "Верните деньги, мошенники!",
    "Никогда больше у вас не куплю."
] * 3 # Размножим

pd.DataFrame(angry_data, columns=["text"]).to_csv("data/demo/2_angry_customers.csv", index=False)
print("✅ Created data/demo/2_angry_customers.csv")

# --- 3. Сложный файл (Разные разделители, пустые строки) ---
# Пишем вручную, чтобы имитировать "грязные" данные от клиента
with open("data/demo/3_dirty_data.csv", "w") as f:
    f.write("msg;date\n") # Точка с запятой вместо запятой!
    f.write("Норм сервис;2023-01-01\n")
    f.write("\n") # Пустая строка
    f.write("Где мой заказ?;2023-01-02\n")
    f.write(";;;\n") # Мусор

print("✅ Created data/demo/3_dirty_data.csv")
