"""
Unit tests for A/B Testing framework.
Tests statistical tests, variant management, and experiment tracking.
"""

import pytest
import os
import sys
import tempfile
import shutil

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from prompt_engineering.ab_testing import (
    ABTester, StatisticalTests, PromptVariant,
    VariantResults, ABTestReport
)


class TestStatisticalTests:
    """Test statistical test calculations."""

    def test_welch_t_test_same_distributions(self):
        """Test Welch's t-test with identical distributions."""
        t_stat, p_value, df = StatisticalTests.welch_t_test(
            mean_a=50, mean_b=50,
            std_a=10, std_b=10,
            n_a=100, n_b=100
        )

        assert t_stat == pytest.approx(0, abs=0.01)
        assert p_value > 0.05  # Not significant

    def test_welch_t_test_different_distributions(self):
        """Test Welch's t-test with different distributions."""
        t_stat, p_value, df = StatisticalTests.welch_t_test(
            mean_a=50, mean_b=70,
            std_a=10, std_b=10,
            n_a=100, n_b=100
        )

        assert abs(t_stat) > 2  # Should be significant
        assert p_value < 0.05   # Significant difference

    def test_cohens_d_no_effect(self):
        """Test Cohen's d with no effect."""
        d = StatisticalTests.cohens_d(
            mean_a=50, mean_b=50,
            std_a=10, std_b=10,
            n_a=100, n_b=100
        )

        assert d == pytest.approx(0, abs=0.01)

    def test_cohens_d_medium_effect(self):
        """Test Cohen's d with medium effect."""
        d = StatisticalTests.cohens_d(
            mean_a=50, mean_b=55,
            std_a=10, std_b=10,
            n_a=100, n_b=100
        )

        # Effect size = (55-50)/10 = 0.5 (medium)
        # Use abs() because direction can be negative
        assert abs(d) > 0.4

    def test_cohens_d_zero_std(self):
        """Test Cohen's d with zero standard deviation."""
        d = StatisticalTests.cohens_d(
            mean_a=50, mean_b=50,
            std_a=0, std_b=0,
            n_a=100, n_b=100
        )

        assert d == 0.0

    def test_p_value_bounds(self):
        """Test that p-value is in valid range."""
        _, p_value, _ = StatisticalTests.welch_t_test(
            mean_a=50, mean_b=100,
            std_a=10, std_b=10,
            n_a=50, n_b=50
        )

        assert 0 <= p_value <= 1


class TestPromptVariant:
    """Test PromptVariant dataclass."""

    def test_variant_creation(self):
        """Test creating a prompt variant."""
        variant = PromptVariant(
            name="test_variant",
            prompt_text="Test prompt {input}",
            version="1.0",
            description="Test description"
        )

        assert variant.name == "test_variant"
        assert "{input}" in variant.prompt_text
        assert variant.version == "1.0"

    def test_variant_minimal(self):
        """Test variant with minimal parameters."""
        variant = PromptVariant(
            name="test",
            prompt_text="Test",
            version="1.0"
        )

        assert variant.name == "test"
        assert variant.description == ""


class TestABTester:
    """Test ABTester class."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for experiments."""
        dir_path = tempfile.mkdtemp()
        yield dir_path
        shutil.rmtree(dir_path)

    @pytest.fixture
    def ab_tester(self, temp_dir):
        """Create an ABTester instance."""
        return ABTester(experiments_dir=temp_dir)

    def test_initialization(self, temp_dir):
        """Test ABTester initialization."""
        tester = ABTester(experiments_dir=temp_dir)
        # experiments_dir may be Path or str, compare string values
        assert str(tester.experiments_dir) == str(temp_dir)

    def test_run_ab_test_basic(self, ab_tester):
        """Test running a basic A/B test."""
        variant_a = PromptVariant(
            name="control",
            prompt_text="Control prompt",
            version="1.0"
        )
        variant_b = PromptVariant(
            name="treatment",
            prompt_text="Treatment prompt",
            version="1.0"
        )

        # Simple executor and metrics functions
        def executor(prompt, data):
            return f"Response to {data}"

        def metrics(output, data):
            return {"accuracy": 0.9}

        test_data = [{"input": f"test{i}"} for i in range(5)]

        report = ab_tester.run_ab_test(
            test_name="basic_test",
            variant_a=variant_a,
            variant_b=variant_b,
            test_data=test_data,
            executor_func=executor,
            metrics_func=metrics,
            primary_metric="accuracy"
        )

        assert isinstance(report, ABTestReport)
        assert report.test_name == "basic_test"

    def test_experiment_persistence(self, ab_tester, temp_dir):
        """Test that experiments are saved."""
        variant_a = PromptVariant(name="a", prompt_text="A", version="1.0")
        variant_b = PromptVariant(name="b", prompt_text="B", version="1.0")

        ab_tester.run_ab_test(
            test_name="persistence_test",
            variant_a=variant_a,
            variant_b=variant_b,
            test_data=[{"input": "test"}],
            executor_func=lambda p, d: "out",
            metrics_func=lambda o, d: {"score": 0.5},
            primary_metric="score"
        )

        # Check that experiment was saved
        experiments = ab_tester.list_experiments()
        assert len(experiments) > 0


class TestVariantResults:
    """Test VariantResults dataclass."""

    def test_results_creation(self):
        """Test creating variant results."""
        variant = PromptVariant(name="test", prompt_text="Test", version="1.0")
        results = VariantResults(
            variant=variant,
            results=[],
            mean_metrics={"accuracy": 0.9},
            std_metrics={"accuracy": 0.05},
            sample_size=100,
            total_latency_ms=1500.0,
            error_count=0
        )

        assert results.sample_size == 100
        assert results.mean_metrics["accuracy"] == 0.9


class TestABTestReport:
    """Test ABTestReport dataclass."""

    def test_report_creation(self):
        """Test creating a test report."""
        variant_a = PromptVariant(name="a", prompt_text="A", version="1.0")
        variant_b = PromptVariant(name="b", prompt_text="B", version="1.0")

        results_a = VariantResults(
            variant=variant_a,
            results=[],
            sample_size=50
        )
        results_b = VariantResults(
            variant=variant_b,
            results=[],
            sample_size=50
        )

        report = ABTestReport(
            test_name="test",
            variant_a=results_a,
            variant_b=results_b,
            winner="Variant B",
            confidence=0.95,
            p_value=0.03,
            effect_size=0.5,
            recommendations=["Use variant B"]
        )

        assert report.winner == "Variant B"
        assert len(report.recommendations) > 0
