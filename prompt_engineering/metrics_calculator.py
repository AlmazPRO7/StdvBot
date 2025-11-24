"""
Comprehensive Metrics Calculator for Prompt Engineering.
Includes classification metrics, text similarity, BLEU score, and link validation.
"""
import re
import math
from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple
from collections import Counter
from urllib.parse import urlparse, parse_qs, unquote_plus


# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class ClassificationMetrics:
    """Classification performance metrics."""
    precision: float
    recall: float
    f1_score: float
    accuracy: float
    support: int


@dataclass
class TextSimilarityMetrics:
    """Text similarity metrics."""
    bleu_1: float
    bleu_2: float
    bleu_4: float
    exact_match: float
    fuzzy_match: float
    word_overlap: float
    levenshtein_ratio: float


@dataclass
class LinkValidationResult:
    """Result of link validation."""
    url: str
    valid: bool
    domain: str
    has_search_param: bool
    has_region_param: bool
    search_query: str
    errors: List[str]


@dataclass
class LinkAccuracyMetrics:
    """Aggregated link accuracy metrics."""
    exact_match_ratio: float
    domain_match_ratio: float
    params_match_ratio: float
    search_query_match_ratio: float
    region_coverage: float
    total_links: int
    valid_links: int


# ============================================================================
# METRICS CALCULATOR
# ============================================================================

class MetricsCalculator:
    """
    Comprehensive metrics calculator for prompt evaluation.

    Supports:
    - Classification metrics (F1, Precision, Recall, Accuracy)
    - Text similarity (BLEU, Exact Match, Fuzzy Match, Levenshtein)
    - Link quality validation
    - Category matching
    """

    # Known domains for construction retail
    KNOWN_DOMAINS = {
        "sdvor.com": {"priority": 1, "region_param": None, "search_param": "freeTextSearch"},
        "market.yandex.ru": {"priority": 2, "region_param": "lr", "search_param": "text"},
        "google.com": {"priority": 3, "region_param": None, "search_param": "q"},
        "www.google.com": {"priority": 3, "region_param": None, "search_param": "q"},
        "avito.ru": {"priority": 4, "region_param": None, "search_param": "q"},
        "www.avito.ru": {"priority": 4, "region_param": None, "search_param": "q"},
    }

    # Yekaterinburg region codes
    YEKATERINBURG_CODES = {
        "lr": ["54"],  # Yandex Market
        "path": ["ekaterinburg", "ekb"],  # Avito, SDVOR
    }

    # ========================================================================
    # CLASSIFICATION METRICS
    # ========================================================================

    def calculate_classification_metrics(
        self,
        tp: int = 0,
        fp: int = 0,
        fn: int = 0,
        tn: int = 0,
        true_positives: int = None,
        false_positives: int = None,
        false_negatives: int = None,
        true_negatives: int = None
    ) -> ClassificationMetrics:
        """
        Calculate classification metrics.

        Args:
            tp/true_positives: True positives
            fp/false_positives: False positives
            fn/false_negatives: False negatives
            tn/true_negatives: True negatives

        Returns:
            ClassificationMetrics with precision, recall, f1, accuracy
        """
        # Support both naming conventions
        tp = true_positives if true_positives is not None else tp
        fp = false_positives if false_positives is not None else fp
        fn = false_negatives if false_negatives is not None else fn
        tn = true_negatives if true_negatives is not None else tn

        total = tp + fp + fn + tn
        if total == 0:
            return ClassificationMetrics(0, 0, 0, 0, 0)

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0

        f1 = 0
        if (precision + recall) > 0:
            f1 = 2 * (precision * recall) / (precision + recall)

        accuracy = (tp + tn) / total

        return ClassificationMetrics(
            precision=precision,
            recall=recall,
            f1_score=f1,
            accuracy=accuracy,
            support=total
        )

    def calculate_multiclass_metrics(
        self,
        predictions: List[str],
        ground_truth: List[str],
        labels: List[str] = None
    ) -> Dict[str, ClassificationMetrics]:
        """
        Calculate per-class and macro metrics for multiclass classification.

        Args:
            predictions: List of predicted labels
            ground_truth: List of true labels
            labels: Optional list of all possible labels

        Returns:
            Dict with per-class metrics and 'macro' average
        """
        if len(predictions) != len(ground_truth):
            raise ValueError("Predictions and ground_truth must have same length")

        if labels is None:
            labels = list(set(predictions + ground_truth))

        results = {}
        all_precision = []
        all_recall = []
        all_f1 = []

        for label in labels:
            tp = sum(1 for p, g in zip(predictions, ground_truth) if p == label and g == label)
            fp = sum(1 for p, g in zip(predictions, ground_truth) if p == label and g != label)
            fn = sum(1 for p, g in zip(predictions, ground_truth) if p != label and g == label)
            tn = sum(1 for p, g in zip(predictions, ground_truth) if p != label and g != label)

            metrics = self.calculate_classification_metrics(tp, fp, fn, tn)
            results[label] = metrics

            all_precision.append(metrics.precision)
            all_recall.append(metrics.recall)
            all_f1.append(metrics.f1_score)

        # Macro average
        n = len(labels)
        results["macro"] = ClassificationMetrics(
            precision=sum(all_precision) / n if n > 0 else 0,
            recall=sum(all_recall) / n if n > 0 else 0,
            f1_score=sum(all_f1) / n if n > 0 else 0,
            accuracy=sum(1 for p, g in zip(predictions, ground_truth) if p == g) / len(predictions) if predictions else 0,
            support=len(predictions)
        )

        return results

    # ========================================================================
    # TEXT SIMILARITY METRICS
    # ========================================================================

    def calculate_text_similarity(
        self,
        prediction: str,
        reference: str
    ) -> TextSimilarityMetrics:
        """
        Calculate comprehensive text similarity metrics.

        Args:
            prediction: Generated text
            reference: Ground truth text

        Returns:
            TextSimilarityMetrics with multiple similarity measures
        """
        # Tokenize
        pred_tokens = self._tokenize(prediction)
        ref_tokens = self._tokenize(reference)

        # BLEU scores
        bleu_1 = self._calculate_bleu(pred_tokens, ref_tokens, n=1)
        bleu_2 = self._calculate_bleu(pred_tokens, ref_tokens, n=2)
        bleu_4 = self._calculate_bleu(pred_tokens, ref_tokens, n=4)

        # Exact match (normalized)
        exact_match = 1.0 if prediction.lower().strip() == reference.lower().strip() else 0.0

        # Fuzzy match (character-level similarity)
        fuzzy_match = self._calculate_fuzzy_match(prediction, reference)

        # Word overlap (Jaccard similarity)
        word_overlap = self._calculate_word_overlap(pred_tokens, ref_tokens)

        # Levenshtein ratio
        levenshtein_ratio = self._calculate_levenshtein_ratio(prediction, reference)

        return TextSimilarityMetrics(
            bleu_1=bleu_1,
            bleu_2=bleu_2,
            bleu_4=bleu_4,
            exact_match=exact_match,
            fuzzy_match=fuzzy_match,
            word_overlap=word_overlap,
            levenshtein_ratio=levenshtein_ratio
        )

    def _tokenize(self, text: str) -> List[str]:
        """Tokenize text into words."""
        return re.findall(r'\w+', text.lower())

    def _calculate_bleu(
        self,
        prediction: List[str],
        reference: List[str],
        n: int = 1
    ) -> float:
        """
        Calculate BLEU-n score.

        Args:
            prediction: Tokenized prediction
            reference: Tokenized reference
            n: N-gram size

        Returns:
            BLEU-n score (0-1)
        """
        if len(prediction) < n or len(reference) < n:
            return 0.0

        # Get n-grams
        pred_ngrams = self._get_ngrams(prediction, n)
        ref_ngrams = self._get_ngrams(reference, n)

        if not pred_ngrams:
            return 0.0

        # Count matches
        pred_counter = Counter(pred_ngrams)
        ref_counter = Counter(ref_ngrams)

        matches = 0
        for ngram, count in pred_counter.items():
            matches += min(count, ref_counter.get(ngram, 0))

        # Precision
        precision = matches / len(pred_ngrams) if pred_ngrams else 0

        # Brevity penalty
        bp = 1.0
        if len(prediction) < len(reference):
            bp = math.exp(1 - len(reference) / len(prediction)) if prediction else 0

        return bp * precision

    def _get_ngrams(self, tokens: List[str], n: int) -> List[Tuple[str, ...]]:
        """Get n-grams from token list."""
        return [tuple(tokens[i:i+n]) for i in range(len(tokens) - n + 1)]

    def _calculate_fuzzy_match(self, s1: str, s2: str) -> float:
        """Calculate fuzzy match ratio using character overlap."""
        if not s1 or not s2:
            return 0.0

        s1_lower = s1.lower()
        s2_lower = s2.lower()

        # Character sets
        chars1 = set(s1_lower)
        chars2 = set(s2_lower)

        intersection = len(chars1 & chars2)
        union = len(chars1 | chars2)

        return intersection / union if union > 0 else 0.0

    def _calculate_word_overlap(
        self,
        tokens1: List[str],
        tokens2: List[str]
    ) -> float:
        """Calculate Jaccard similarity between word sets."""
        if not tokens1 or not tokens2:
            return 0.0

        set1 = set(tokens1)
        set2 = set(tokens2)

        intersection = len(set1 & set2)
        union = len(set1 | set2)

        return intersection / union if union > 0 else 0.0

    def _calculate_levenshtein_ratio(self, s1: str, s2: str) -> float:
        """
        Calculate normalized Levenshtein similarity.

        Returns:
            Similarity ratio (0-1), where 1 is identical
        """
        if not s1 and not s2:
            return 1.0
        if not s1 or not s2:
            return 0.0

        # Levenshtein distance
        m, n = len(s1), len(s2)
        dp = [[0] * (n + 1) for _ in range(m + 1)]

        for i in range(m + 1):
            dp[i][0] = i
        for j in range(n + 1):
            dp[0][j] = j

        for i in range(1, m + 1):
            for j in range(1, n + 1):
                cost = 0 if s1[i-1].lower() == s2[j-1].lower() else 1
                dp[i][j] = min(
                    dp[i-1][j] + 1,      # deletion
                    dp[i][j-1] + 1,      # insertion
                    dp[i-1][j-1] + cost  # substitution
                )

        distance = dp[m][n]
        max_len = max(m, n)

        return 1.0 - (distance / max_len) if max_len > 0 else 1.0

    # ========================================================================
    # LINK VALIDATION
    # ========================================================================

    def validate_link(self, url: str) -> LinkValidationResult:
        """
        Validate a single URL for construction retail context.

        Args:
            url: URL to validate

        Returns:
            LinkValidationResult with validation details
        """
        errors = []

        try:
            parsed = urlparse(url)
        except Exception as e:
            return LinkValidationResult(
                url=url,
                valid=False,
                domain="",
                has_search_param=False,
                has_region_param=False,
                search_query="",
                errors=[f"Invalid URL: {e}"]
            )

        domain = parsed.netloc.lower().replace("www.", "")
        params = parse_qs(parsed.query)

        # Check domain
        domain_info = self.KNOWN_DOMAINS.get(domain) or self.KNOWN_DOMAINS.get(parsed.netloc)

        has_search_param = False
        search_query = ""
        has_region_param = False

        if domain_info:
            # Check search parameter
            search_param = domain_info.get("search_param")
            if search_param:
                if search_param in params:
                    has_search_param = True
                    search_query = unquote_plus(params[search_param][0])
                else:
                    errors.append(f"Missing search parameter: {search_param}")

            # Check region parameter
            region_param = domain_info.get("region_param")
            if region_param:
                if region_param in params:
                    has_region_param = True
                    region_value = params[region_param][0]
                    expected_codes = self.YEKATERINBURG_CODES.get(region_param, [])
                    if expected_codes and region_value not in expected_codes:
                        errors.append(f"Wrong region code: {region_value} (expected: {expected_codes})")
                else:
                    errors.append(f"Missing region parameter: {region_param}")

            # Check path-based region (Avito, SDVOR)
            path_lower = parsed.path.lower()
            for region_code in self.YEKATERINBURG_CODES.get("path", []):
                if region_code in path_lower:
                    has_region_param = True
                    break
        else:
            errors.append(f"Unknown domain: {domain}")

        valid = len(errors) == 0 or (has_search_param and len(errors) <= 1)

        return LinkValidationResult(
            url=url,
            valid=valid,
            domain=domain,
            has_search_param=has_search_param,
            has_region_param=has_region_param,
            search_query=search_query,
            errors=errors
        )

    def validate_sdvor_link(self, url: str) -> Dict[str, bool]:
        """
        Specifically validate SDVOR link format.

        Args:
            url: URL to validate

        Returns:
            Dict with validation flags
        """
        result = {
            "valid_domain": False,
            "has_freeTextSearch": False,
            "has_category": False,
            "correct_encoding": False,
            "no_region_prefix": True  # /ekb/ is legacy
        }

        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower().replace("www.", "")

            result["valid_domain"] = domain == "sdvor.com"

            params = parse_qs(parsed.query)
            if "freeTextSearch" in params:
                result["has_freeTextSearch"] = True
                query = params["freeTextSearch"][0]
                # Check encoding (+ should be used for spaces)
                result["correct_encoding"] = "+" in url or "%20" in url or " " not in query

            # Check for category link
            if "/category/" in parsed.path:
                result["has_category"] = True

            # Legacy /ekb/ prefix check
            result["no_region_prefix"] = "/ekb/" not in parsed.path

        except Exception:
            pass

        return result

    def calculate_link_accuracy(
        self,
        predicted_links: List[str],
        ground_truth_links: List[str],
        check_params: bool = True
    ) -> LinkAccuracyMetrics:
        """
        Calculate accuracy metrics for predicted links.

        Args:
            predicted_links: List of predicted URLs
            ground_truth_links: List of correct URLs
            check_params: Whether to check query parameters

        Returns:
            LinkAccuracyMetrics with various accuracy measures
        """
        if not predicted_links:
            return LinkAccuracyMetrics(0, 0, 0, 0, 0, 0, 0)

        exact_matches = 0
        domain_matches = 0
        params_matches = 0
        query_matches = 0
        region_count = 0
        valid_count = 0

        # Validate all predicted links
        validations = [self.validate_link(url) for url in predicted_links]

        for i, pred_url in enumerate(predicted_links):
            validation = validations[i]

            if validation.valid:
                valid_count += 1

            if validation.has_region_param:
                region_count += 1

            # Compare with ground truth if available
            if i < len(ground_truth_links):
                gt_url = ground_truth_links[i]
                gt_validation = self.validate_link(gt_url)

                # Exact match
                if pred_url.lower() == gt_url.lower():
                    exact_matches += 1

                # Domain match
                if validation.domain == gt_validation.domain:
                    domain_matches += 1

                # Search query match
                if validation.search_query and gt_validation.search_query:
                    if self._normalize_query(validation.search_query) == self._normalize_query(gt_validation.search_query):
                        query_matches += 1

                # Parameters match (approximate)
                if check_params:
                    pred_params = parse_qs(urlparse(pred_url).query)
                    gt_params = parse_qs(urlparse(gt_url).query)
                    if self._params_similar(pred_params, gt_params):
                        params_matches += 1

        n = len(predicted_links)
        n_gt = min(n, len(ground_truth_links))

        return LinkAccuracyMetrics(
            exact_match_ratio=exact_matches / n_gt if n_gt > 0 else 0,
            domain_match_ratio=domain_matches / n_gt if n_gt > 0 else 0,
            params_match_ratio=params_matches / n_gt if n_gt > 0 else 0,
            search_query_match_ratio=query_matches / n_gt if n_gt > 0 else 0,
            region_coverage=region_count / n if n > 0 else 0,
            total_links=n,
            valid_links=valid_count
        )

    def _normalize_query(self, query: str) -> str:
        """Normalize search query for comparison."""
        return re.sub(r'\s+', ' ', query.lower().strip())

    def _params_similar(self, params1: Dict, params2: Dict) -> bool:
        """Check if two parameter dicts are similar."""
        # Consider similar if key overlap is > 50%
        keys1 = set(params1.keys())
        keys2 = set(params2.keys())

        if not keys1 or not keys2:
            return False

        overlap = len(keys1 & keys2)
        total = len(keys1 | keys2)

        return overlap / total > 0.5 if total > 0 else False

    # ========================================================================
    # CATEGORY MATCHING
    # ========================================================================

    def calculate_category_accuracy(
        self,
        predicted_categories: List[str],
        ground_truth_categories: List[str]
    ) -> Dict[str, float]:
        """
        Calculate category prediction accuracy.

        Args:
            predicted_categories: Predicted category names
            ground_truth_categories: True category names

        Returns:
            Dict with exact_match, fuzzy_match, and partial_match ratios
        """
        if not predicted_categories or not ground_truth_categories:
            return {"exact_match": 0, "fuzzy_match": 0, "partial_match": 0}

        exact = 0
        fuzzy = 0
        partial = 0

        for pred, gt in zip(predicted_categories, ground_truth_categories):
            pred_norm = pred.lower().strip()
            gt_norm = gt.lower().strip()

            # Exact match
            if pred_norm == gt_norm:
                exact += 1
                fuzzy += 1
                partial += 1
            # Fuzzy match (Levenshtein > 0.8)
            elif self._calculate_levenshtein_ratio(pred_norm, gt_norm) > 0.8:
                fuzzy += 1
                partial += 1
            # Partial match (one contains the other)
            elif pred_norm in gt_norm or gt_norm in pred_norm:
                partial += 1

        n = min(len(predicted_categories), len(ground_truth_categories))

        return {
            "exact_match": exact / n if n > 0 else 0,
            "fuzzy_match": fuzzy / n if n > 0 else 0,
            "partial_match": partial / n if n > 0 else 0
        }


# ============================================================================
# QUICK TEST
# ============================================================================

def run_test():
    """Run quick test to verify metrics calculator."""
    calc = MetricsCalculator()

    print("=" * 60)
    print("METRICS CALCULATOR TEST")
    print("=" * 60)

    # 1. Classification metrics
    print("\n1. Classification Metrics:")
    metrics = calc.calculate_classification_metrics(tp=45, fp=5, fn=10, tn=40)
    print(f"   Precision: {metrics.precision:.3f}")
    print(f"   Recall: {metrics.recall:.3f}")
    print(f"   F1 Score: {metrics.f1_score:.3f}")
    print(f"   Accuracy: {metrics.accuracy:.3f}")

    # 2. Text similarity
    print("\n2. Text Similarity:")
    pred = "Bosch GSR 12V-15 Дрель-шуруповерт"
    ref = "Bosch GSR 12V-15 Дрель-шуруповёрт аккумуляторная"
    sim = calc.calculate_text_similarity(pred, ref)
    print(f"   Prediction: {pred}")
    print(f"   Reference: {ref}")
    print(f"   BLEU-1: {sim.bleu_1:.3f}")
    print(f"   BLEU-4: {sim.bleu_4:.3f}")
    print(f"   Word Overlap: {sim.word_overlap:.3f}")
    print(f"   Levenshtein: {sim.levenshtein_ratio:.3f}")

    # 3. Link validation
    print("\n3. Link Validation:")
    links = [
        "https://sdvor.com/search?freeTextSearch=Bosch+GSR+12V-15",
        "https://market.yandex.ru/search?text=Bosch+GSR&lr=54",
        "https://www.avito.ru/ekaterinburg?q=Bosch+GSR",
    ]
    for url in links:
        result = calc.validate_link(url)
        status = "✅" if result.valid else "❌"
        print(f"   {status} {result.domain}: search='{result.search_query}' region={result.has_region_param}")

    # 4. SDVOR specific
    print("\n4. SDVOR Link Validation:")
    sdvor_result = calc.validate_sdvor_link("https://sdvor.com/search?freeTextSearch=Bosch+GSR+12V-15")
    for key, value in sdvor_result.items():
        status = "✅" if value else "❌"
        print(f"   {status} {key}")

    print("\n" + "=" * 60)
    print("All tests completed!")
    print("=" * 60)


if __name__ == "__main__":
    run_test()
