import pandas as pd
import json
from sklearn.metrics import classification_report, confusion_matrix, accuracy_score

# Функция для восстановления "Истины" (в реальности эту колонку заполняют люди)
def get_ground_truth(text):
    text = text.lower()
    if "ужас" in text or "бой" in text or "хамил" in text or "цвет" in text:
        return "complaint"
    elif "нужен" in text or "доставка" in text:
        return "sales"
    return "unknown"

print("📊 ЗАГРУЗКА ОТЧЕТА AI...")
try:
    # Загружаем отчет, который сделал main.py
    df = pd.read_csv("data/final_report.csv")
except FileNotFoundError:
    print("❌ Файл data/final_report.csv не найден. Сначала запусти main.py!")
    exit()

# 1. Парсим колонку 'analysis' (она сохранилась как строка JSON, надо вернуть в объект)
# В main.py мы сохраняли весь dict, pandas превратил его в строку "{'intent': ...}"
# Нам нужно достать оттуда 'intent'.
predicted_intents = []
for item in df['analysis']:
    try:
        # Pandas иногда сохраняет dict как строку с одинарными кавычками, что не валидный JSON
        # Используем eval (только для своих данных!) или json.loads если формат верный
        if isinstance(item, str):
            # Простой хак для строк типа "{'a': 1}" -> dict
            data = eval(item) 
        else:
            data = item
        
        intent = data.get('intent', 'unknown')
        if intent:
            predicted_intents.append(intent.lower())
        else:
            predicted_intents.append("unknown")
            
    except Exception as e:
        predicted_intents.append("error")

# 2. Генерируем эталонные ответы (Ground Truth)
true_intents = df['msg'].apply(get_ground_truth).tolist()

# 3. Считаем метрики (SKLEARN POWER)
print("\n" + "="*40)
print("🏆 РЕЗУЛЬТАТЫ ТЕСТИРОВАНИЯ МОДЕЛИ")
print("="*40)

# Accuracy - общий процент попаданий
acc = accuracy_score(true_intents, predicted_intents)
print(f"\n✅ ОБЩАЯ ТОЧНОСТЬ (ACCURACY): {acc:.2%} \n")

# Детальный отчет (F1-score, Precision, Recall)
print("📋 ДЕТАЛЬНЫЙ ОТЧЕТ (Classification Report):")
print(classification_report(true_intents, predicted_intents, target_names=["Жалоба (Complaint)", "Продажа (Sales)"]))

# Матрица ошибок (Кто с кем перепутался)
print("\n🧩 МАТРИЦА ОШИБОК (Confusion Matrix):")
cm = confusion_matrix(true_intents, predicted_intents)
print(f"Истинные Жалобы, распознанные как Жалобы: {cm[0][0]}")
print(f"Истинные Жалобы, распознанные как Продажи (ОШИБКА!): {cm[0][1]}")
print(f"Истинные Продажи, распознанные как Жалобы (ОШИБКА!): {cm[1][0]}")
print(f"Истинные Продажи, распознанные как Продажи: {cm[1][1]}")
