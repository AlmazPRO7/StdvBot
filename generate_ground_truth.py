import pandas as pd
import random
import os

# Генерируем данные СРАЗУ с правильными метками (Labels)
data = []

# Sales
for _ in range(30):
    msg = f"Куплю цемент {random.randint(1,10)} мешков."
    data.append({"text": msg, "true_intent": "sales"})

# Complaints
for _ in range(30):
    msg = f"Брак! Верните деньги за {random.randint(100,900)} заказ!"
    data.append({"text": msg, "true_intent": "complaint"})

# Questions
for _ in range(20):
    msg = "Как проехать на склад?"
    data.append({"text": msg, "true_intent": "question"})

df = pd.DataFrame(data)
os.makedirs("data", exist_ok=True)
df.to_csv("data/ground_truth.csv", index=False)
print("✅ Ground Truth dataset created.")
