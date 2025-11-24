#!/usr/bin/env python3
"""
Prompt Engineering CLI - Главный инструмент промпт-инженера

Команды:
  metrics     - Рассчитать метрики качества промпта
  ab-test     - Запустить A/B тест между промптами
  prompt      - Управление версиями промптов
  benchmark   - Бенчмарк промпта на тестовых данных
  report      - Генерация отчётов
  judge       - LLM-as-a-Judge оценка
  augment     - Аугментация датасета
  optimize    - Авто-оптимизация промпта
  plot        - Построение графиков

Примеры:
  ./prompt_engineering_cli.py metrics --test-results results.json
  ./prompt_engineering_cli.py plot --type history --data history.json
"""

import sys
import argparse
import json
from pathlib import Path

# Добавить корень проекта в path
sys.path.insert(0, str(Path(__file__).parent.parent))

from prompt_engineering.metrics_calculator import MetricsCalculator
from prompt_engineering.ab_testing import ABTester, PromptVariant
from prompt_engineering.prompt_manager import PromptManager
from prompt_engineering.advanced_tools import LLMJudge, DatasetAugmenter, PromptOptimizer
from prompt_engineering.visualization import Visualizer


class PromptEngineeringCLI:
    """CLI для работы с промптами"""

    def __init__(self):
        self.metrics_calc = MetricsCalculator()
        self.ab_tester = ABTester()
        self.prompt_manager = PromptManager()
        self.judge = LLMJudge()
        self.augmenter = DatasetAugmenter()
        self.optimizer = PromptOptimizer()
        self.visualizer = Visualizer()

    # === PLOT ===
    def cmd_plot(self, args):
        """Команда: Визуализация"""
        print(f"\n{'='*80}")
        print("📈 ПОСТРОЕНИЕ ГРАФИКОВ")
        print(f"{'='*80}")
        
        if not args.data:
            print("❌ Укажите --data (JSON файл)")
            return

        with open(args.data, 'r') as f:
            data = json.load(f)

        if args.type == 'history':
            path = self.visualizer.plot_version_history(data)
            print(f"✅ График истории сохранен: {path}")
            
        elif args.type == 'confusion':
            path = self.visualizer.plot_confusion_matrix(
                data['y_true'], data['y_pred'], data['labels']
            )
            print(f"✅ Матрица ошибок сохранена: {path}")
            
        elif args.type == 'judge':
            path = self.visualizer.plot_judge_distribution(data)
            print(f"✅ Гистограмма сохранена: {path}")

    # === JUDGE ===
    def cmd_judge(self, args):
        """Команда: LLM-as-a-Judge"""
        print(f"\n{'='*80}")
        print("⚖️ LLM СУДЬЯ")
        print(f"{'='*80}")
        
        result = self.judge.evaluate(
            question=args.question,
            answer=args.answer,
            ground_truth=args.ground_truth,
            criteria=args.criteria or "accuracy"
        )
        
        print(f"\n🏆 Оценка: {result.score}/5")
        print(f"📝 Обоснование: {result.reasoning}")

    # === AUGMENT ===
    def cmd_augment(self, args):
        """Команда: Аугментация данных"""
        print(f"\n{'='*80}")
        print("🧬 ГЕНЕРАЦИЯ ВАРИАЦИЙ (Augmentation)")
        print(f"{'='*80}")
        
        examples = []
        if args.input:
            with open(args.input, 'r') as f:
                examples = json.load(f)
        elif args.text:
            examples = [args.text]
            
        print(f"Входные данные: {len(examples)} примеров")
        print("Генерирую...")
        
        variations = self.augmenter.augment(examples, n_variations=args.n)
        
        print(f"\n✅ Сгенерировано {len(variations)} новых примеров:\n")
        for v in variations:
            print(f"  - {v}")
            
        if args.output:
            with open(args.output, 'w') as f:
                json.dump(variations, f, ensure_ascii=False, indent=2)
            print(f"\nСохранено в {args.output}")

    # === OPTIMIZE ===
    def cmd_optimize(self, args):
        """Команда: Оптимизация промпта"""
        print(f"\n{'='*80}")
        print("✨ АВТО-ОПТИМИЗАЦИЯ ПРОМПТА")
        print(f"{'='*80}")
        
        # Получить текущий промпт
        try:
            current_prompt = self.prompt_manager.get_prompt(args.prompt_name).prompt_text
        except:
            print(f"❌ Промпт '{args.prompt_name}' не найден")
            return
        
        # Загрузить ошибки
        with open(args.failures, 'r') as f:
            failures = json.load(f)
            
        print(f"Анализ {len(failures)} ошибок...")
        optimized_text = self.optimizer.optimize(current_prompt, failures)
        
        print("\n💡 ПРЕДЛОЖЕННЫЙ ПРОМПТ:\n")
        print(optimized_text)
        
        if input("\nСохранить новую версию? (y/n): ").lower() == 'y':
            self.prompt_manager.update_prompt(
                prompt_name=args.prompt_name,
                prompt_text=optimized_text,
                description="Auto-optimized",
                author="OptimizerAI"
            )
            print("✅ Сохранено!")

    def cmd_metrics(self, args):
        """Команда: расчёт метрик"""
        print(f"\n{'='*80}")
        print("📊 РАСЧЁТ МЕТРИК")
        print(f"{'='*80}")

        if args.test_results:
            with open(args.test_results, 'r', encoding='utf-8') as f:
                results = json.load(f)

            print(f"\nЗагружено тестов: {len(results.get('results', []))}")

            if args.metrics_type == "classification":
                tp = args.true_positives or 0
                fp = args.false_positives or 0
                fn = args.false_negatives or 0
                tn = args.true_negatives or 0

                result = self.metrics_calc.calculate_classification_metrics(tp, fp, fn, tn)

                print(f"\n✅ Classification Metrics:")
                print(f"  Precision: {result.precision:.3f}")
                print(f"  Recall: {result.recall:.3f}")
                print(f"  F1 Score: {result.f1_score:.3f}")
                print(f"  Accuracy: {result.accuracy:.3f}")
                print(f"  Support: {result.support}")

        print(f"\n✅ Метрики рассчитаны!")

    def cmd_ab_test(self, args):
        """Команда: A/B тестирование"""
        print(f"\n{'='*80}")
        print("🧪 A/B ТЕСТИРОВАНИЕ")
        print(f"{'='*80}")

        try:
            prompt_a = self.prompt_manager.get_prompt(args.variant_a)
            print(f"✅ Загружен вариант A: {args.variant_a} (v{prompt_a.version})")
        except:
            print(f"❌ Промпт '{args.variant_a}' не найден")
            return

        try:
            prompt_b = self.prompt_manager.get_prompt(args.variant_b)
            print(f"✅ Загружен вариант B: {args.variant_b} (v{prompt_b.version})")
        except:
            print(f"❌ Промпт '{args.variant_b}' не найден")
            return

        if args.test_data:
            with open(args.test_data, 'r', encoding='utf-8') as f:
                test_data = json.load(f)
            print(f"✅ Загружено тестовых данных: {len(test_data)}")
            print("\n⚠️ A/B тест требует executor_func и metrics_func")
            print("💡 Используйте Python API для полного функционала")
        else:
            print("❌ Не указан файл с тестовыми данными (--test-data)")

    def cmd_prompt(self, args):
        """Команда: управление промптами"""
        print(f"\n{'='*80}")
        print("📝 УПРАВЛЕНИЕ ПРОМПТАМИ")
        print(f"{'='*80}")

        if args.action == "list":
            prompts = self.prompt_manager.list_prompts()
            if not prompts:
                print("\nНет сохранённых промптов")
            else:
                print(f"\nВсего промптов: {len(prompts)}\n")
                for p in prompts:
                    print(f"  📄 {p['name']}")
                    print(f"     Текущая версия: v{p['current_version']}")
                    print(f"     Всего версий: {p['total_versions']}")
                    print(f"     Создан: {p['created_at'][:10]}")
                    print()

        elif args.action == "create":
            if not args.name or not args.text:
                print("❌ Укажите --name и --text")
                return
            prompt = self.prompt_manager.create_prompt(
                prompt_name=args.name,
                prompt_text=args.text,
                description=args.description or "No description",
                author=args.author or "prompt_engineer"
            )
            print(f"\n✅ Создан промпт '{args.name}' версия {prompt.version}")

        elif args.action == "update":
            if not args.name or not args.text:
                print("❌ Укажите --name и --text")
                return
            prompt = self.prompt_manager.update_prompt(
                prompt_name=args.name,
                prompt_text=args.text,
                description=args.description or "Update",
                version_type=args.version_type or "minor",
                author=args.author or "prompt_engineer"
            )
            print(f"\n✅ Обновлён промпт '{args.name}' версия {prompt.version}")

        elif args.action == "show":
            if not args.name:
                print("❌ Укажите --name")
                return
            prompt = self.prompt_manager.get_prompt(args.name, args.version)
            print(f"\n📄 Промпт: {args.name}")
            print(f"Версия: v{prompt.version}")
            print(f"Автор: {prompt.author}")
            print(f"Описание: {prompt.description}")
            print(f"\nТекст промпта:\n{'-'*80}\n{prompt.prompt_text}\n{'-'*80}")

        elif args.action == "versions":
            if not args.name:
                print("❌ Укажите --name")
                return
            versions = self.prompt_manager.list_versions(args.name)
            print(f"\nВерсии промпта '{args.name}':\n")
            for v in versions:
                print(f"  • v{v}")

        elif args.action == "compare":
            if not args.name or not args.version or not args.version2:
                print("❌ Укажите --name, --version и --version2")
                return
            comparison = self.prompt_manager.compare_versions(args.name, args.version, args.version2)
            print(f"\n🔍 Сравнение версий {args.version} и {args.version2}:")
            print(f"Схожесть: {comparison['similarity']*100:.1f}%")
            print(f"Длина: {comparison['length_a']} → {comparison['length_b']}")
            print(f"\nDiff:")
            for line in comparison['diff']:
                print(f"  {line}")

        elif args.action == "export":
            if not args.name:
                print("❌ Укажите --name")
                return
            export_data = self.prompt_manager.export_prompt(args.name, args.version)
            if args.output:
                with open(args.output, 'w', encoding='utf-8') as f:
                    f.write(export_data)
                print(f"✅ Промпт экспортирован: {args.output}")
            else:
                print(export_data)

    def cmd_benchmark(self, args):
        print(f"\n{'='*80}\n⚡ BENCHMARK\n{'='*80}")
        print("\n⚠️ Benchmark требует integration с Vision API")

    def cmd_report(self, args):
        print(f"\n{'='*80}\n📊 ГЕНЕРАЦИЯ ОТЧЁТОВ\n{'='*80}")
        if args.experiment_dir:
            print(f"\nАнализ экспериментов в {args.experiment_dir}")
            exp_dir = Path(args.experiment_dir)
            if not exp_dir.exists():
                print(f"❌ Директория не найдена: {args.experiment_dir}")
                return
            reports = list(exp_dir.glob("**/report.json"))
            print(f"Найдено отчётов: {len(reports)}\n")
            for report_file in reports:
                with open(report_file, 'r', encoding='utf-8') as f:
                    report = json.load(f)
                print(f"  📄 {report['test_name']}")
                print(f"     Победитель: {report['winner']}")
                print(f"     Уверенность: {report['confidence']*100:.1f}%")
                print()
        else:
            print("❌ Укажите --experiment-dir")


def main():
    parser = argparse.ArgumentParser(description="Prompt Engineering CLI", formatter_class=argparse.RawDescriptionHelpFormatter)
    subparsers = parser.add_subparsers(dest='command', help='Команды')

    # === METRICS ===
    metrics_parser = subparsers.add_parser('metrics', help='Расчёт метрик')
    metrics_parser.add_argument('--test-results', help='JSON результаты')
    metrics_parser.add_argument('--metrics-type', choices=['classification'], default='classification')
    metrics_parser.add_argument('--true-positives', type=int)
    metrics_parser.add_argument('--false-positives', type=int)
    metrics_parser.add_argument('--false-negatives', type=int)
    metrics_parser.add_argument('--true-negatives', type=int)

    # === A/B TEST ===
    ab_parser = subparsers.add_parser('ab-test', help='A/B тестирование')
    ab_parser.add_argument('--variant-a', required=True)
    ab_parser.add_argument('--variant-b', required=True)
    ab_parser.add_argument('--test-data')
    ab_parser.add_argument('--sample-size', type=int)

    # === PROMPT ===
    prompt_parser = subparsers.add_parser('prompt', help='Управление промптами')
    prompt_parser.add_argument('action', choices=['list', 'create', 'update', 'show', 'versions', 'compare', 'export'])
    prompt_parser.add_argument('--name')
    prompt_parser.add_argument('--text')
    prompt_parser.add_argument('--description')
    prompt_parser.add_argument('--author')
    prompt_parser.add_argument('--version')
    prompt_parser.add_argument('--version2')
    prompt_parser.add_argument('--version-type', choices=['major', 'minor', 'patch'])
    prompt_parser.add_argument('--output')

    # === BENCHMARK ===
    benchmark_parser = subparsers.add_parser('benchmark', help='Бенчмарк промпта')
    benchmark_parser.add_argument('--prompt', required=True)
    benchmark_parser.add_argument('--dataset', required=True)
    benchmark_parser.add_argument('--output')

    # === REPORT ===
    report_parser = subparsers.add_parser('report', help='Генерация отчётов')
    report_parser.add_argument('--experiment-dir')

    # === JUDGE ===
    judge_parser = subparsers.add_parser('judge', help='Оценка ответа через LLM')
    judge_parser.add_argument('--question', required=True)
    judge_parser.add_argument('--answer', required=True)
    judge_parser.add_argument('--ground-truth')
    judge_parser.add_argument('--criteria')

    # === AUGMENT ===
    augment_parser = subparsers.add_parser('augment', help='Генерация синтетических данных')
    augment_parser.add_argument('--text')
    augment_parser.add_argument('--input')
    augment_parser.add_argument('--output')
    augment_parser.add_argument('--n', type=int, default=3)

    # === OPTIMIZE ===
    opt_parser = subparsers.add_parser('optimize', help='Авто-улучшение промпта')
    opt_parser.add_argument('--prompt-name', required=True)
    opt_parser.add_argument('--failures', required=True)

    # === PLOT ===
    plot_parser = subparsers.add_parser('plot', help='Построение графиков')
    plot_parser.add_argument('--type', choices=['history', 'confusion', 'judge'], required=True)
    plot_parser.add_argument('--data', required=True)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    cli = PromptEngineeringCLI()

    if args.command == 'metrics': cli.cmd_metrics(args)
    elif args.command == 'ab-test': cli.cmd_ab_test(args)
    elif args.command == 'prompt': cli.cmd_prompt(args)
    elif args.command == 'benchmark': cli.cmd_benchmark(args)
    elif args.command == 'report': cli.cmd_report(args)
    elif args.command == 'judge': cli.cmd_judge(args)
    elif args.command == 'augment': cli.cmd_augment(args)
    elif args.command == 'optimize': cli.cmd_optimize(args)
    elif args.command == 'plot': cli.cmd_plot(args)

if __name__ == "__main__":
    main()