import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
import json
from typing import List, Dict
import os

class Visualizer:
    """
    Инструмент для визуализации метрик промпт-инжиниринга.
    """
    
    def __init__(self, output_dir="reports/plots"):
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)
        # Настройка стиля
        sns.set_theme(style="whitegrid")
        plt.rcParams['figure.figsize'] = (10, 6)

    def plot_confusion_matrix(self, y_true, y_pred, labels, title="Confusion Matrix"):
        """
        Строит матрицу ошибок для задач классификации.
        """
        from sklearn.metrics import confusion_matrix
        
        cm = confusion_matrix(y_true, y_pred, labels=labels)
        
        plt.figure(figsize=(10, 8))
        sns.heatmap(cm, annot=True, fmt='d', cmap='Blues', xticklabels=labels, yticklabels=labels)
        plt.title(title)
        plt.ylabel('Истина (True)')
        plt.xlabel('Предсказание (Pred)')
        
        path = f"{self.output_dir}/confusion_matrix.png"
        plt.savefig(path)
        plt.close()
        return path

    def plot_version_history(self, history_data: List[Dict]):
        """
        Строит график изменения метрик по версиям промпта.
        history_data = [{'version': '1.0', 'f1': 0.8}, {'version': '1.1', 'f1': 0.85}]
        """
        df = pd.DataFrame(history_data)
        
        plt.figure()
        sns.lineplot(data=df, x='version', y='f1', marker='o', label='F1 Score')
        if 'accuracy' in df.columns:
            sns.lineplot(data=df, x='version', y='accuracy', marker='s', label='Accuracy')
            
        plt.title("Эволюция качества промпта")
        plt.ylim(0, 1.0)
        plt.ylabel("Score")
        plt.xlabel("Версия")
        
        path = f"{self.output_dir}/version_history.png"
        plt.savefig(path)
        plt.close()
        return path

    def plot_judge_distribution(self, scores: List[int]):
        """
        Гистограмма оценок LLM-судьи (1-5).
        """
        plt.figure()
        sns.countplot(x=scores, palette="viridis")
        plt.title("Распределение оценок LLM-судьи")
        plt.xlabel("Оценка (1-5)")
        plt.ylabel("Количество")
        plt.xlim(0.5, 5.5)
        
        path = f"{self.output_dir}/judge_dist.png"
        plt.savefig(path)
        plt.close()
        return path

    def plot_ab_comparison(self, results: Dict[str, float], metric_name="Win Rate"):
        """
        Сравнивает два (или более) варианта промптов (A/B тест).
        results = {'Prompt A': 0.85, 'Prompt B': 0.92}
        """
        plt.figure()
        df = pd.DataFrame(list(results.items()), columns=['Variant', 'Score'])
        
        # Красивый барплот
        ax = sns.barplot(data=df, x='Variant', y='Score', palette=['#95a5a6', '#2ecc71'])
        
        # Добавляем значения над столбцами
        for i, v in enumerate(df['Score']):
            ax.text(i, v + 0.01, f"{v:.2f}", ha='center', va='bottom', fontweight='bold')
            
        plt.title(f"A/B Testing Results ({metric_name})")
        plt.ylim(0, 1.1)
        plt.ylabel(metric_name)
        
        path = f"{self.output_dir}/ab_comparison.png"
        plt.savefig(path)
        plt.close()
        return path
