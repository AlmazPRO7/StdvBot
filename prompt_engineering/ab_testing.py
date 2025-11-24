"""
A/B Testing Framework for Prompt Engineering.
Supports statistical significance testing, experiment tracking, and reporting.
"""
import json
import os
import time
import logging
import math
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Callable, Optional, Any
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class PromptVariant:
    """Represents a prompt variant for A/B testing."""
    name: str
    prompt_text: str
    version: str
    description: str = ""


@dataclass
class TestResult:
    """Result of a single test case."""
    input_data: Dict
    output: str
    metrics: Dict[str, float]
    latency_ms: float
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    error: Optional[str] = None


@dataclass
class VariantResults:
    """Aggregated results for a variant."""
    variant: PromptVariant
    results: List[TestResult]
    mean_metrics: Dict[str, float] = field(default_factory=dict)
    std_metrics: Dict[str, float] = field(default_factory=dict)
    sample_size: int = 0
    total_latency_ms: float = 0.0
    error_count: int = 0


@dataclass
class ABTestReport:
    """Complete A/B test report."""
    test_name: str
    variant_a: VariantResults
    variant_b: VariantResults
    winner: str  # "Variant A", "Variant B", "No significant difference"
    confidence: float  # 0.0 - 1.0
    p_value: float
    effect_size: float
    recommendations: List[str]
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    duration_seconds: float = 0.0


# ============================================================================
# STATISTICAL FUNCTIONS
# ============================================================================

class StatisticalTests:
    """Statistical significance tests for A/B testing."""

    @staticmethod
    def welch_t_test(mean_a: float, mean_b: float, std_a: float, std_b: float,
                     n_a: int, n_b: int) -> tuple:
        """
        Welch's t-test for unequal variances.

        Returns:
            tuple: (t_statistic, p_value, degrees_of_freedom)
        """
        if n_a < 2 or n_b < 2:
            return 0.0, 1.0, 0

        # Variance of means
        var_a = (std_a ** 2) / n_a if n_a > 0 else 0
        var_b = (std_b ** 2) / n_b if n_b > 0 else 0

        if var_a + var_b == 0:
            return 0.0, 1.0, 0

        # t-statistic
        t_stat = (mean_a - mean_b) / math.sqrt(var_a + var_b)

        # Welch-Satterthwaite degrees of freedom
        numerator = (var_a + var_b) ** 2
        denominator = (var_a ** 2) / (n_a - 1) + (var_b ** 2) / (n_b - 1)

        if denominator == 0:
            return t_stat, 1.0, 0

        df = numerator / denominator

        # Approximate p-value using t-distribution
        # Using a simplified approximation for |t| -> p
        p_value = StatisticalTests._t_to_p(abs(t_stat), df)

        return t_stat, p_value, df

    @staticmethod
    def _t_to_p(t: float, df: float) -> float:
        """
        Approximate p-value from t-statistic using normal approximation.
        For large df, t-distribution approaches normal.
        """
        if df <= 0:
            return 1.0

        # For df > 30, use normal approximation
        if df > 30:
            # Two-tailed p-value from z-score
            z = t
            # Error function approximation
            p = 2 * (1 - StatisticalTests._normal_cdf(z))
            return max(0.0, min(1.0, p))

        # For smaller df, use approximation
        x = df / (df + t ** 2)
        p = StatisticalTests._incomplete_beta(df / 2, 0.5, x)
        return max(0.0, min(1.0, p))

    @staticmethod
    def _normal_cdf(x: float) -> float:
        """Approximate CDF of standard normal distribution."""
        # Approximation using error function
        return 0.5 * (1 + math.erf(x / math.sqrt(2)))

    @staticmethod
    def _incomplete_beta(a: float, b: float, x: float) -> float:
        """Simplified incomplete beta function approximation."""
        # Very rough approximation for our use case
        if x <= 0:
            return 0.0
        if x >= 1:
            return 1.0
        return x ** a * (1 - x) ** b * (a + b) / a

    @staticmethod
    def cohens_d(mean_a: float, mean_b: float, std_a: float, std_b: float,
                 n_a: int, n_b: int) -> float:
        """
        Calculate Cohen's d effect size.

        Interpretation:
        - 0.2: small effect
        - 0.5: medium effect
        - 0.8: large effect
        """
        # Pooled standard deviation
        if n_a + n_b - 2 <= 0:
            return 0.0

        pooled_std = math.sqrt(
            ((n_a - 1) * std_a ** 2 + (n_b - 1) * std_b ** 2) / (n_a + n_b - 2)
        )

        if pooled_std == 0:
            return 0.0

        return (mean_a - mean_b) / pooled_std

    @staticmethod
    def calculate_confidence(p_value: float) -> float:
        """Convert p-value to confidence level."""
        return 1.0 - p_value

    @staticmethod
    def required_sample_size(effect_size: float = 0.5, power: float = 0.8,
                             alpha: float = 0.05) -> int:
        """
        Calculate required sample size for detecting effect.

        Args:
            effect_size: Expected Cohen's d
            power: Desired statistical power (1 - beta)
            alpha: Significance level

        Returns:
            Required sample size per group
        """
        # Simplified calculation
        # n = 2 * ((z_alpha + z_beta) / d)^2

        z_alpha = 1.96 if alpha == 0.05 else 2.58  # 95% or 99%
        z_beta = 0.84 if power == 0.8 else 1.28    # 80% or 90%

        if effect_size == 0:
            return 100  # Default

        n = 2 * ((z_alpha + z_beta) / effect_size) ** 2
        return max(10, int(math.ceil(n)))


# ============================================================================
# A/B TESTER
# ============================================================================

class ABTester:
    """
    A/B Testing framework for prompt comparison.

    Features:
    - Statistical significance testing (Welch's t-test)
    - Effect size calculation (Cohen's d)
    - Experiment tracking and persistence
    - Automated recommendations
    """

    def __init__(self, experiments_dir: str = "prompt_engineering/experiments"):
        self.experiments_dir = Path(experiments_dir)
        self.experiments_dir.mkdir(parents=True, exist_ok=True)
        self.stats = StatisticalTests()

    def run_ab_test(
        self,
        test_name: str,
        variant_a: PromptVariant,
        variant_b: PromptVariant,
        test_data: List[Dict],
        executor_func: Callable[[str, Dict], str],
        metrics_func: Callable[[str, Dict], Dict[str, float]],
        sample_size: Optional[int] = None,
        primary_metric: str = "accuracy"
    ) -> ABTestReport:
        """
        Run A/B test comparing two prompt variants.

        Args:
            test_name: Name for this experiment
            variant_a: First prompt variant (usually baseline)
            variant_b: Second prompt variant (usually new version)
            test_data: List of test cases (dicts with input data)
            executor_func: Function(prompt_text, data) -> output
            metrics_func: Function(output, data) -> {metric: value}
            sample_size: Number of samples (None = use all test_data)
            primary_metric: Main metric for winner determination

        Returns:
            ABTestReport with results and recommendations
        """
        start_time = time.time()

        logger.info(f"🧪 Starting A/B test: {test_name}")
        logger.info(f"   Variant A: {variant_a.name} (v{variant_a.version})")
        logger.info(f"   Variant B: {variant_b.name} (v{variant_b.version})")

        # Determine sample size
        if sample_size is None:
            sample_size = len(test_data)
        else:
            sample_size = min(sample_size, len(test_data))

        test_samples = test_data[:sample_size]
        logger.info(f"   Test samples: {sample_size}")

        # Run tests for each variant
        results_a = self._run_variant_tests(variant_a, test_samples, executor_func, metrics_func)
        results_b = self._run_variant_tests(variant_b, test_samples, executor_func, metrics_func)

        # Calculate aggregate metrics
        self._calculate_aggregate_metrics(results_a)
        self._calculate_aggregate_metrics(results_b)

        # Statistical analysis on primary metric
        mean_a = results_a.mean_metrics.get(primary_metric, 0)
        mean_b = results_b.mean_metrics.get(primary_metric, 0)
        std_a = results_a.std_metrics.get(primary_metric, 0)
        std_b = results_b.std_metrics.get(primary_metric, 0)
        n_a = results_a.sample_size
        n_b = results_b.sample_size

        # Welch's t-test
        t_stat, p_value, df = self.stats.welch_t_test(
            mean_a, mean_b, std_a, std_b, n_a, n_b
        )

        # Effect size
        effect_size = self.stats.cohens_d(mean_a, mean_b, std_a, std_b, n_a, n_b)

        # Confidence
        confidence = self.stats.calculate_confidence(p_value)

        # Determine winner
        winner = self._determine_winner(mean_a, mean_b, p_value, effect_size)

        # Generate recommendations
        recommendations = self._generate_recommendations(
            results_a, results_b, winner, p_value, effect_size, primary_metric
        )

        # Create report
        report = ABTestReport(
            test_name=test_name,
            variant_a=results_a,
            variant_b=results_b,
            winner=winner,
            confidence=confidence,
            p_value=p_value,
            effect_size=effect_size,
            recommendations=recommendations,
            duration_seconds=time.time() - start_time
        )

        # Save experiment
        self._save_experiment(test_name, report)

        # Log results
        logger.info(f"✅ A/B test completed in {report.duration_seconds:.2f}s")
        logger.info(f"   Winner: {winner}")
        logger.info(f"   Confidence: {confidence*100:.1f}%")
        logger.info(f"   P-value: {p_value:.4f}")
        logger.info(f"   Effect size: {effect_size:.3f}")

        return report

    def _run_variant_tests(
        self,
        variant: PromptVariant,
        test_data: List[Dict],
        executor_func: Callable,
        metrics_func: Callable
    ) -> VariantResults:
        """Run tests for a single variant."""
        results = []

        for i, data in enumerate(test_data):
            start = time.time()
            error = None
            output = ""
            metrics = {}

            try:
                output = executor_func(variant.prompt_text, data)
                metrics = metrics_func(output, data)
            except Exception as e:
                error = str(e)
                logger.warning(f"⚠️ Test {i+1} failed for {variant.name}: {e}")

            latency_ms = (time.time() - start) * 1000

            result = TestResult(
                input_data=data,
                output=output,
                metrics=metrics,
                latency_ms=latency_ms,
                error=error
            )
            results.append(result)

            # Progress
            if (i + 1) % 10 == 0:
                logger.info(f"   {variant.name}: {i+1}/{len(test_data)} tests...")

        return VariantResults(
            variant=variant,
            results=results,
            sample_size=len(results),
            error_count=sum(1 for r in results if r.error)
        )

    def _calculate_aggregate_metrics(self, variant_results: VariantResults):
        """Calculate mean and std for all metrics."""
        if not variant_results.results:
            return

        # Collect all metrics
        all_metrics = {}
        for result in variant_results.results:
            if result.error:
                continue
            for metric, value in result.metrics.items():
                if metric not in all_metrics:
                    all_metrics[metric] = []
                all_metrics[metric].append(value)

        # Calculate mean and std
        for metric, values in all_metrics.items():
            if values:
                n = len(values)
                mean = sum(values) / n
                variance = sum((x - mean) ** 2 for x in values) / n if n > 1 else 0
                std = math.sqrt(variance)

                variant_results.mean_metrics[metric] = mean
                variant_results.std_metrics[metric] = std

        # Total latency
        variant_results.total_latency_ms = sum(
            r.latency_ms for r in variant_results.results
        )

    def _determine_winner(self, mean_a: float, mean_b: float,
                          p_value: float, effect_size: float) -> str:
        """Determine winner based on statistical analysis."""
        # Significance threshold
        alpha = 0.05

        if p_value > alpha:
            return "No significant difference"

        # Significant difference found
        if mean_b > mean_a:
            if abs(effect_size) >= 0.2:  # At least small effect
                return "Variant B"
            else:
                return "Variant B (marginal)"
        else:
            if abs(effect_size) >= 0.2:
                return "Variant A"
            else:
                return "Variant A (marginal)"

    def _generate_recommendations(
        self,
        results_a: VariantResults,
        results_b: VariantResults,
        winner: str,
        p_value: float,
        effect_size: float,
        primary_metric: str
    ) -> List[str]:
        """Generate actionable recommendations."""
        recommendations = []

        # Sample size recommendations
        if results_a.sample_size < 30:
            required = self.stats.required_sample_size(effect_size=0.5)
            recommendations.append(
                f"⚠️ Sample size ({results_a.sample_size}) is small. "
                f"Recommend at least {required} samples for reliable results."
            )

        # Statistical significance
        if p_value > 0.05:
            recommendations.append(
                "📊 No statistically significant difference detected (p > 0.05). "
                "Consider running more tests or checking for implementation issues."
            )
        elif p_value < 0.01:
            recommendations.append(
                "✅ Highly significant result (p < 0.01). "
                "Confident in the difference between variants."
            )

        # Effect size interpretation
        if abs(effect_size) < 0.2:
            recommendations.append(
                "📉 Effect size is small. The practical difference may be minimal."
            )
        elif abs(effect_size) >= 0.8:
            recommendations.append(
                "📈 Large effect size! The difference is practically significant."
            )

        # Winner-based recommendations
        if "Variant B" in winner:
            recommendations.append(
                f"🎯 Recommendation: Deploy {results_b.variant.name} (v{results_b.variant.version})"
            )

            # Check for regressions in other metrics
            for metric in results_a.mean_metrics:
                if metric != primary_metric:
                    if results_b.mean_metrics.get(metric, 0) < results_a.mean_metrics.get(metric, 0) * 0.9:
                        recommendations.append(
                            f"⚠️ Warning: {metric} regressed in Variant B. "
                            "Review before deployment."
                        )

        elif "Variant A" in winner:
            recommendations.append(
                f"🎯 Recommendation: Keep {results_a.variant.name} (v{results_a.variant.version})"
            )
        else:
            recommendations.append(
                "🔄 Consider iterating on Variant B or collecting more data."
            )

        # Error rate check
        error_rate_a = results_a.error_count / max(1, results_a.sample_size)
        error_rate_b = results_b.error_count / max(1, results_b.sample_size)

        if error_rate_a > 0.1 or error_rate_b > 0.1:
            recommendations.append(
                f"🚨 High error rate detected (A: {error_rate_a:.1%}, B: {error_rate_b:.1%}). "
                "Review test implementation."
            )

        return recommendations

    def _save_experiment(self, test_name: str, report: ABTestReport):
        """Save experiment results to disk."""
        # Create experiment directory
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        exp_dir = self.experiments_dir / f"{test_name}_{timestamp}"
        exp_dir.mkdir(parents=True, exist_ok=True)

        # Helper to convert dataclass to dict
        def to_dict(obj):
            if hasattr(obj, '__dataclass_fields__'):
                result = {}
                for field_name in obj.__dataclass_fields__:
                    value = getattr(obj, field_name)
                    result[field_name] = to_dict(value)
                return result
            elif isinstance(obj, list):
                return [to_dict(item) for item in obj]
            elif isinstance(obj, dict):
                return {k: to_dict(v) for k, v in obj.items()}
            else:
                return obj

        # Save main report
        report_dict = to_dict(report)
        with open(exp_dir / "report.json", "w", encoding="utf-8") as f:
            json.dump(report_dict, f, indent=2, ensure_ascii=False, default=str)

        # Save variant A results
        results_a_dict = to_dict(report.variant_a)
        with open(exp_dir / "variant_a_results.json", "w", encoding="utf-8") as f:
            json.dump(results_a_dict, f, indent=2, ensure_ascii=False, default=str)

        # Save variant B results
        results_b_dict = to_dict(report.variant_b)
        with open(exp_dir / "variant_b_results.json", "w", encoding="utf-8") as f:
            json.dump(results_b_dict, f, indent=2, ensure_ascii=False, default=str)

        logger.info(f"📁 Experiment saved to: {exp_dir}")

    def list_experiments(self) -> List[Dict]:
        """List all saved experiments."""
        experiments = []
        for exp_dir in sorted(self.experiments_dir.iterdir()):
            if exp_dir.is_dir():
                report_path = exp_dir / "report.json"
                if report_path.exists():
                    with open(report_path, "r") as f:
                        report = json.load(f)
                        experiments.append({
                            "name": report.get("test_name"),
                            "timestamp": report.get("timestamp"),
                            "winner": report.get("winner"),
                            "confidence": report.get("confidence"),
                            "path": str(exp_dir)
                        })
        return experiments

    def load_experiment(self, experiment_path: str) -> Dict:
        """Load a saved experiment."""
        exp_dir = Path(experiment_path)
        report_path = exp_dir / "report.json"

        if not report_path.exists():
            raise FileNotFoundError(f"Experiment not found: {experiment_path}")

        with open(report_path, "r") as f:
            return json.load(f)


# ============================================================================
# QUICK TEST FUNCTION
# ============================================================================

def run_quick_test():
    """Run a quick test to verify the framework works."""
    import random

    # Mock executor
    def mock_executor(prompt: str, data: dict) -> str:
        time.sleep(0.1)  # Simulate API call
        return f"Response for {data.get('product', 'unknown')}"

    # Mock metrics
    def mock_metrics(output: str, data: dict) -> dict:
        # Simulate metrics with some variance
        is_optimized = "детально" in output or len(output) > 20
        base = 0.85 if is_optimized else 0.65
        return {
            "accuracy": base + random.uniform(-0.1, 0.1),
            "f1_score": base + random.uniform(-0.05, 0.05),
            "latency_score": 1.0 - random.uniform(0, 0.2)
        }

    # Test data
    test_data = [
        {"product": "BOSCH GSR 12V-15", "type": "drill"},
        {"product": "MAKITA DF330", "type": "drill"},
        {"product": "KNAUF Rotband", "type": "plaster"},
        {"product": "Профиль 27x28", "type": "profile"},
        {"product": "Саморезы 3.5x25", "type": "screws"},
    ]

    # Variants
    variant_a = PromptVariant(
        name="Baseline",
        prompt_text="Опиши товар.",
        version="1.0",
        description="Простой промпт"
    )

    variant_b = PromptVariant(
        name="Optimized",
        prompt_text="Проанализируй товар детально: бренд, модель, характеристики.",
        version="2.0",
        description="Детальный промпт"
    )

    # Run test
    tester = ABTester()
    report = tester.run_ab_test(
        test_name="quick_test",
        variant_a=variant_a,
        variant_b=variant_b,
        test_data=test_data,
        executor_func=mock_executor,
        metrics_func=mock_metrics,
        primary_metric="accuracy"
    )

    # Print report
    print("\n" + "="*60)
    print("A/B TEST REPORT")
    print("="*60)
    print(f"Winner: {report.winner}")
    print(f"Confidence: {report.confidence*100:.1f}%")
    print(f"P-value: {report.p_value:.4f}")
    print(f"Effect size: {report.effect_size:.3f}")
    print("\nRecommendations:")
    for rec in report.recommendations:
        print(f"  {rec}")
    print("="*60)

    return report


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_quick_test()
