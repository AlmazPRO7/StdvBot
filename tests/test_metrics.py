"""
Unit tests for MetricsCalculator.
Tests BLEU scores, text similarity, and link validation.
"""

import pytest
import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from prompt_engineering.metrics_calculator import (
    MetricsCalculator,
    ClassificationMetrics,
    TextSimilarityMetrics,
    LinkValidationResult,
    LinkAccuracyMetrics
)


@pytest.fixture
def calculator():
    """Create a MetricsCalculator instance."""
    return MetricsCalculator()


class TestClassificationMetrics:
    """Test classification metrics calculation."""

    def test_perfect_precision(self, calculator):
        """Test perfect precision (no false positives)."""
        result = calculator.calculate_classification_metrics(
            tp=10, fp=0, fn=5, tn=100
        )

        assert result.precision == 1.0

    def test_perfect_recall(self, calculator):
        """Test perfect recall (no false negatives)."""
        result = calculator.calculate_classification_metrics(
            tp=10, fp=5, fn=0, tn=100
        )

        assert result.recall == 1.0

    def test_f1_score(self, calculator):
        """Test F1 score calculation."""
        result = calculator.calculate_classification_metrics(
            tp=80, fp=20, fn=20, tn=100
        )

        # F1 = 2 * (precision * recall) / (precision + recall)
        # precision = 80/100 = 0.8, recall = 80/100 = 0.8
        # F1 = 2 * 0.8 * 0.8 / 1.6 = 0.8
        assert result.f1_score == pytest.approx(0.8, rel=0.01)

    def test_zero_division_handling(self, calculator):
        """Test handling of zero division cases."""
        result = calculator.calculate_classification_metrics(
            tp=0, fp=0, fn=0, tn=100
        )

        assert result.precision == 0.0
        assert result.recall == 0.0
        assert result.f1_score == 0.0

    def test_accuracy(self, calculator):
        """Test accuracy calculation."""
        result = calculator.calculate_classification_metrics(
            tp=70, fp=10, fn=10, tn=10
        )

        # accuracy = (tp + tn) / (tp + tn + fp + fn) = 80/100 = 0.8
        assert result.accuracy == pytest.approx(0.8, rel=0.01)


class TestTextSimilarity:
    """Test text similarity metrics."""

    def test_exact_match(self, calculator):
        """Test exact match detection."""
        result = calculator.calculate_text_similarity(
            "Hello world",
            "Hello world"
        )

        assert isinstance(result, TextSimilarityMetrics)
        # Exact match should give high similarity
        assert result.exact_match > 0.9

    def test_different_texts(self, calculator):
        """Test different texts."""
        result = calculator.calculate_text_similarity(
            "Hello world",
            "Goodbye moon"
        )

        assert isinstance(result, TextSimilarityMetrics)
        assert result.exact_match < 1.0

    def test_bleu_scores(self, calculator):
        """Test BLEU score calculation."""
        result = calculator.calculate_text_similarity(
            "The cat sat on the mat",
            "The cat sat on the mat"
        )

        assert result.bleu_1 == pytest.approx(1.0, rel=0.01)
        assert result.bleu_2 == pytest.approx(1.0, rel=0.01)
        assert result.bleu_4 == pytest.approx(1.0, rel=0.01)

    def test_partial_bleu(self, calculator):
        """Test partial BLEU scores."""
        result = calculator.calculate_text_similarity(
            "The cat sat on the mat",
            "The cat is on the floor"
        )

        # Should have some overlap but not perfect
        assert 0 < result.bleu_1 < 1

    def test_levenshtein_ratio(self, calculator):
        """Test Levenshtein ratio."""
        result = calculator.calculate_text_similarity(
            "kitten",
            "sitting"
        )

        # Should be similar but not identical
        assert 0 < result.levenshtein_ratio < 1


class TestLinkValidation:
    """Test link validation."""

    def test_valid_sdvor_link(self, calculator):
        """Test valid sdvor.com link."""
        result = calculator.validate_link(
            "https://sdvor.com/search?freeTextSearch=плитка"
        )

        assert isinstance(result, LinkValidationResult)
        assert result.valid is True
        assert "sdvor.com" in result.domain

    def test_malformed_link(self, calculator):
        """Test malformed link."""
        result = calculator.validate_link("not a valid url")

        assert isinstance(result, LinkValidationResult)
        assert result.valid is False

    def test_sdvor_link_with_search(self, calculator):
        """Test sdvor.com link with search parameter."""
        result = calculator.validate_link(
            "https://sdvor.com/search?freeTextSearch=дрель+makita"
        )

        assert result.valid is True
        assert result.has_search_param is True


class TestLinkAccuracy:
    """Test link accuracy calculation."""

    def test_perfect_accuracy(self, calculator):
        """Test perfect link accuracy."""
        predicted = [
            "https://sdvor.com/search?freeTextSearch=a",
            "https://sdvor.com/search?freeTextSearch=b"
        ]
        ground_truth = [
            "https://sdvor.com/search?freeTextSearch=a",
            "https://sdvor.com/search?freeTextSearch=b"
        ]

        result = calculator.calculate_link_accuracy(predicted, ground_truth)

        assert isinstance(result, LinkAccuracyMetrics)
        assert result.exact_match_ratio == 1.0

    def test_domain_match(self, calculator):
        """Test domain match ratio."""
        predicted = [
            "https://sdvor.com/search?freeTextSearch=different",
            "https://sdvor.com/product/123"
        ]
        ground_truth = [
            "https://sdvor.com/search?freeTextSearch=original",
            "https://sdvor.com/product/123"
        ]

        result = calculator.calculate_link_accuracy(predicted, ground_truth)

        # Domain should match even if params differ
        assert result.domain_match_ratio == 1.0


class TestMulticlassMetrics:
    """Test multiclass metrics calculation."""

    def test_multiclass_basic(self, calculator):
        """Test basic multiclass metrics."""
        predictions = ["sales", "complaint", "sales", "tech_support"]
        ground_truth = ["sales", "complaint", "complaint", "tech_support"]

        result = calculator.calculate_multiclass_metrics(
            predictions, ground_truth, ["sales", "complaint", "tech_support"]
        )

        # Result should be dict with per-class metrics
        assert isinstance(result, dict)
        # Should have macro metrics
        assert "macro" in result
        # Should have per-class metrics
        assert "sales" in result or "complaint" in result

    def test_multiclass_per_class(self, calculator):
        """Test per-class metrics."""
        predictions = ["A", "A", "B", "B"]
        ground_truth = ["A", "A", "B", "A"]

        result = calculator.calculate_multiclass_metrics(
            predictions, ground_truth, ["A", "B"]
        )

        assert isinstance(result, dict)
        # Should contain class labels
        assert "A" in result or "B" in result


class TestCategoryAccuracy:
    """Test category accuracy calculation."""

    def test_perfect_category_match(self, calculator):
        """Test perfect category matching."""
        predicted = ["sales", "complaint", "tech_support"]
        ground_truth = ["sales", "complaint", "tech_support"]

        result = calculator.calculate_category_accuracy(predicted, ground_truth)

        # Result is dict with different match types
        assert isinstance(result, dict)
        assert result.get("exact_match", result.get("accuracy", 0)) == 1.0

    def test_partial_category_match(self, calculator):
        """Test partial category matching."""
        predicted = ["sales", "spam", "tech_support"]
        ground_truth = ["sales", "complaint", "tech_support"]

        result = calculator.calculate_category_accuracy(predicted, ground_truth)

        # Should be approximately 2/3
        match_value = result.get("exact_match", result.get("accuracy", 0))
        assert match_value == pytest.approx(2/3, rel=0.01)

    def test_empty_lists(self, calculator):
        """Test empty lists."""
        result = calculator.calculate_category_accuracy([], [])

        assert isinstance(result, dict)
