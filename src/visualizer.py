import matplotlib
matplotlib.use('Agg') # Важно для сервера без монитора!
import matplotlib.pyplot as plt
import io
import pandas as pd

def create_dashboard(df):
    """
    Принимает DataFrame и возвращает объект байтов (картинку)
    """
    # Стиль графиков (похож на ggplot)
    plt.style.use('ggplot')
    
    # Создаем холст 15x5 дюймов с 3 графиками
    fig, axes = plt.subplots(1, 3, figsize=(18, 6))
    fig.suptitle('Construction AI Analytics Dashboard', fontsize=20, fontweight='bold')

    # --- 1. Intent Distribution (Pie Chart) ---
    if 'intent' in df.columns:
        intent_counts = df['intent'].value_counts()
        axes[0].pie(intent_counts, labels=intent_counts.index, autopct='%1.1f%%', startangle=140, colors=['#ff9999','#66b3ff','#99ff99','#ffcc99'])
        axes[0].set_title('Типы обращений (Intent)')
    
    # --- 2. Sentiment Analysis (Donut Chart) ---
    if 'sentiment' in df.columns:
        sent_counts = df['sentiment'].value_counts()
        # Рисуем круг
        axes[1].pie(sent_counts, labels=sent_counts.index, autopct='%1.1f%%', colors=['#ff6666', '#ffff99', '#66ff66'])
        # Рисуем белый круг в центре (делаем пончик)
        centre_circle = plt.Circle((0,0),0.70,fc='white')
        axes[1].add_artist(centre_circle)
        axes[1].set_title('Настроение (Sentiment)')

    # --- 3. Urgency Level (Bar Chart) ---
    if 'urgency' in df.columns:
        urgency_counts = df['urgency'].value_counts()
        bars = axes[2].bar(urgency_counts.index, urgency_counts.values, color=['#ff4d4d', '#4da6ff'])
        axes[2].set_title('Срочность (Urgency)')
        axes[2].set_ylabel('Кол-во заявок')
        
    plt.tight_layout()
    
    # Сохраняем в память (RAM), а не на диск
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=100)
    buf.seek(0)
    plt.close(fig)
    
    return buf
