from typing import Dict, Any, List, Tuple
import re
from difflib import SequenceMatcher


class Scorer:
    def __init__(self, method: str = "hybrid"):
        self.method = method
    
    def score(self, response: str, expected: str) -> Tuple[float, str, Dict[str, Any]]:
        """Dispatches to the selected scoring method (exact, fuzzy, keyword, or hybrid)."""
        response_lower = response.lower().strip()
        expected_lower = expected.lower().strip()
        
        if self.method == "exact":
            return self._exact_match(response_lower, expected_lower)
        elif self.method == "fuzzy":
            return self._fuzzy_match(response_lower, expected_lower)
        elif self.method == "keyword":
            return self._keyword_match(response_lower, expected_lower)
        else:
            return self._hybrid_scoring(response_lower, expected_lower)
    
    def _exact_match(self, response: str, expected: str) -> Tuple[float, str, Dict[str, Any]]:
        """Returns 1.0 only if the strings are identical after lowercasing and stripping."""
        if response == expected:
            return 1.0, "pass", {}
        return 0.0, "fail", {"reason": "exact mismatch"}
    
    def _fuzzy_match(self, response: str, expected: str) -> Tuple[float, str, Dict[str, Any]]:
        """Ratcliff/Obershelp sequence matching. >= 0.8 is pass, >= 0.5 is partial."""
        ratio = SequenceMatcher(None, response, expected).ratio()
        if ratio >= 0.8:
            return ratio, "pass", {"similarity": ratio}
        elif ratio >= 0.5:
            return ratio, "partial", {"similarity": ratio}
        return ratio, "fail", {"similarity": ratio, "reason": "low similarity"}
    
    def _keyword_match(self, response: str, expected: str) -> Tuple[float, str, Dict[str, Any]]:
        """Recall-based keyword overlap: |common| / |expected|.

        Uses recall rather than Jaccard (|common| / |union|) so that a verbose
        correct response isn't penalised for including helpful extra context.
        """
        expected_keywords = set(re.findall(r'\w+', expected.lower()))
        response_keywords = set(re.findall(r'\w+', response.lower()))
        
        common = expected_keywords & response_keywords
        match_ratio = len(common) / len(expected_keywords) if expected_keywords else 0
        
        if match_ratio == 1.0:
            return 1.0, "pass", {"matched_keywords": list(common)}
        elif match_ratio >= 0.5:
            return match_ratio, "partial", {"matched_keywords": list(common)}
        return match_ratio, "fail", {"matched_keywords": list(common)}
    
    def _hybrid_scoring(self, response: str, expected: str) -> Tuple[float, str, Dict[str, Any]]:
        """Cascading hybrid: exact (O(n)) -> keyword (O(n)) -> fuzzy (O(n*m)).

        Exact match is the highest bar. Keyword uses recall-based ratio so verbose
        correct answers still pass. Fuzzy catches paraphrases with character-level
        similarity. Each sub-method has its own threshold. A gap exists where
        keyword_ratio 0.4-0.8 with fuzzy < 0.5 drops to 0 — this is intentional:
        for short factual answers, if neither 80% keyword overlap nor 50% character
        similarity exists, the response is likely wrong. For long-form generation
        evaluation, a blended score would be more appropriate.
        """
        response_lower = response.lower()
        expected_lower = expected.lower()
        
        if response_lower == expected_lower:
            return 1.0, "pass", {"method": "exact"}
        
        expected_keywords = set(re.findall(r'\w+', expected_lower))
        response_keywords = set(re.findall(r'\w+', response_lower))
        common = expected_keywords & response_keywords
        keyword_ratio = len(common) / len(expected_keywords) if expected_keywords else 0
        
        if keyword_ratio >= 0.8:
            return keyword_ratio, "pass", {"method": "keyword", "matched": list(common)}
        
        ratio = SequenceMatcher(None, response_lower, expected_lower).ratio()
        if ratio >= 0.5:
            status = "pass" if ratio >= 0.7 else "partial"
            return ratio, status, {"method": "fuzzy", "similarity": ratio}
        
        return 0.0, "fail", {"method": "hybrid", "reason": "all methods failed"}


def calculate_pass_rate(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Aggregates results into pass/fail/partial counts and a weighted pass rate.
    
    Partials count as 0.5 toward the pass rate (partial credit).
    """
    total = len(results)
    if total == 0:
        return {"pass_rate": 0.0, "total": 0, "passed": 0, "failed": 0, "partial": 0}
    
    passed = sum(1 for r in results if r["status"] == "pass")
    failed = sum(1 for r in results if r["status"] == "fail")
    partial = sum(1 for r in results if r["status"] == "partial")
    
    return {
        "pass_rate": (passed + 0.5 * partial) / total,
        "total": total,
        "passed": passed,
        "failed": failed,
        "partial": partial
    }


def generate_summary(results: List[Dict[str, Any]], scoring_method: str) -> Dict[str, Any]:
    """Wraps pass-rate data with the scoring method and full results list for export."""
    summary = calculate_pass_rate(results)
    summary["scoring_method"] = scoring_method
    summary["results"] = results
    return summary