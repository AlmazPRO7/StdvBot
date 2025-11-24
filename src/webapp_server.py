import logging
import datetime
import sys
import os
import json
import plotly
import plotly.graph_objs as go
import random
from flask import Flask, render_template

# Path Hack
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from src.prompts import ANALYST_SYSTEM_PROMPT, SUPPORT_AGENT_SYSTEM_PROMPT, POLICY_AGENT_SYSTEM_PROMPT

app = Flask(__name__)
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

def get_recent_logs():
    """Generates mock logs."""
    intents = ["sales", "complaint", "tech_support", "policy_question"]
    queries = [
        "Где заказ #5521?", "Срочно 10 мешков Ротбанда", 
        "Шуруповерт искрит", "Возврат без чека возможен?",
        "Доставка опоздала", "Цена на гипсокартон?",
        "Как получить карту Профи?", "Какой клей для плитки?"
    ]
    logs = []
    for i in range(12):
        latency = round(random.uniform(0.5, 1.8), 2)
        logs.append({
            "id": f"ID-{9920+i}",
            "time": (datetime.datetime.now() - datetime.timedelta(minutes=i*4)).strftime("%H:%M"),
            "intent": random.choice(intents),
            "query": random.choice(queries),
            "latency": latency,
            "status": "OK" if latency < 1.5 else "SLOW"
        })
    return logs

def create_plots():
    """Generates CLEAN, STATIC-ready plots."""
    
    common_layout = dict(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color='#8b949e', family="Segoe UI, sans-serif", size=11),
        margin=dict(t=30, l=30, r=20, b=30),
        showlegend=False
    )

    # 1. Confusion Matrix (Clean Heatmap)
    z = [[50, 2, 0], [1, 48, 1], [0, 1, 45]]
    x = ['Sales', 'Complaint', 'Tech']
    y = ['Sales', 'Complaint', 'Tech']
    confusion = go.Figure(data=go.Heatmap(
        z=z, x=x, y=y,
        colorscale=[[0, '#0d1117'], [1, '#238636']], # Black to Green
        showscale=False,
        text=z, texttemplate="%{text}", 
        textfont={"size": 14, "color": "white"}
    ))
    confusion.update_layout(**common_layout)
    confusion.update_layout(title="Intent Accuracy", title_font_size=14, title_x=0.05)

    # 2. Latency (Area Chart instead of Histogram for cleaner look)
    y_vals = [random.uniform(0.8, 1.4) for _ in range(20)]
    latency = go.Figure(data=go.Scatter(
        y=y_vals,
        fill='tozeroy',
        mode='lines',
        line=dict(width=2, color='#58a6ff'),
        fillcolor='rgba(88, 166, 255, 0.2)'
    ))
    latency.update_layout(**common_layout)
    latency.update_layout(
        title="Avg Latency (ms)", title_font_size=14, title_x=0.05,
        xaxis=dict(showgrid=False, showticklabels=False),
        yaxis=dict(showgrid=True, gridcolor='#21262d', showticklabels=True)
    )

    # 3. A/B Test (Side by Side Bar)
    ab = go.Figure(data=[
        go.Bar(name='V1', x=['Accuracy', 'Safety'], y=[75, 80], marker_color='#30363d', text=['75%','80%'], textposition='auto'),
        go.Bar(name='V2', x=['Accuracy', 'Safety'], y=[96, 99], marker_color='#a371f7', text=['96%','99%'], textposition='auto')
    ])
    ab.update_layout(**common_layout)
    ab.update_layout(
        title="Prompt V1 vs V2", title_font_size=14, title_x=0.05,
        barmode='group', showlegend=True, 
        legend=dict(orientation="h", y=1.1, x=0.5, xanchor='center')
    )

    # 4. RAG (Donut)
    rag = go.Figure(data=[go.Pie(
        labels=['Returns', 'Delivery', 'Loyalty', 'Services'],
        values=[35, 30, 20, 15],
        hole=.7,
        marker=dict(colors=['#d2a8ff', '#58a6ff', '#238636', '#da3633']),
        textinfo='percent',
        textfont=dict(color='white')
    )])
    rag.update_layout(**common_layout)
    rag.update_layout(title="Knowledge Topics", title_font_size=14, title_x=0.5, title_xanchor='center')

    return json.dumps({
        "confusion": confusion, "latency": latency, "ab": ab, "rag": rag
    }, cls=plotly.utils.PlotlyJSONEncoder)

@app.route('/')
def index():
    return render_template('dashboard.html', 
                           graphJSON=create_plots(), 
                           logs=get_recent_logs(),
                           prompts={"analyst": ANALYST_SYSTEM_PROMPT, "support": SUPPORT_AGENT_SYSTEM_PROMPT, "policy": POLICY_AGENT_SYSTEM_PROMPT})

if __name__ == '__main__':
    print("🚀 WebApp Server running on http://0.0.0.0:5000")
    app.run(host='0.0.0.0', port=5000)