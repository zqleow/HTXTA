import unittest
import json
import tempfile
import os
from pathlib import Path

from test_loader import TestLoader
from scorer import Scorer, calculate_pass_rate, generate_summary
from endpoint_client import MockEndpointClient
from main import build_prompt


class TestTestLoader(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.valid_test_file = os.path.join(self.temp_dir, "valid.jsonl")
        self.invalid_test_file = os.path.join(self.temp_dir, "invalid.jsonl")
        
        with open(self.valid_test_file, 'w') as f:
            f.write('{"id": "q1", "input": "What is the leave policy?", "expected": "14 days"}\n')
            f.write('{"id": "q2", "input": "Who approves claims?", "expected": "Manager"}\n')
    
    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir)
    
    def test_load_valid_file(self):
        loader = TestLoader(self.valid_test_file)
        test_cases = loader.load()
        self.assertEqual(len(test_cases), 2)
        self.assertEqual(test_cases[0]["id"], "q1")
    
    def test_load_missing_file(self):
        loader = TestLoader("nonexistent.jsonl")
        with self.assertRaises(FileNotFoundError):
            loader.load()
    
    def test_load_invalid_json(self):
        with open(self.invalid_test_file, 'w') as f:
            f.write('{"id": "q1", invalid json}')
        loader = TestLoader(self.invalid_test_file)
        with self.assertRaises(ValueError):
            loader.load()
    
    def test_load_missing_fields(self):
        with open(self.invalid_test_file, 'w') as f:
            f.write('{"id": "q1"}\n')
        loader = TestLoader(self.invalid_test_file)
        with self.assertRaises(ValueError):
            loader.load()
    
    def test_validate_valid_cases(self):
        loader = TestLoader(self.valid_test_file)
        test_cases = loader.load()
        self.assertTrue(loader.validate(test_cases))


class TestScorer(unittest.TestCase):
    def setUp(self):
        self.scorer = Scorer(method="hybrid")
    
    def test_exact_match(self):
        scorer = Scorer(method="exact")
        score, status, details = scorer.score("14 days annual leave", "14 days annual leave")
        self.assertEqual(score, 1.0)
        self.assertEqual(status, "pass")
    
    def test_exact_no_match(self):
        scorer = Scorer(method="exact")
        score, status, details = scorer.score("14 days", "14 days annual leave")
        self.assertEqual(score, 0.0)
        self.assertEqual(status, "fail")
    
    def test_case_insensitivity(self):
        scorer = Scorer(method="exact")
        score, status, details = scorer.score("14 DAYS ANNUAL LEAVE", "14 days annual leave")
        self.assertEqual(score, 1.0)
    
    def test_fuzzy_match(self):
        scorer = Scorer(method="fuzzy")
        score, status, details = scorer.score("14 days annual leave", "14 days")
        self.assertGreater(score, 0.5)
    
    def test_fuzzy_high_similarity(self):
        scorer = Scorer(method="fuzzy")
        score, status, details = scorer.score("14 days annual leave", "14 days annual")
        self.assertEqual(status, "pass")
    
    def test_fuzzy_low_similarity(self):
        scorer = Scorer(method="fuzzy")
        score, status, details = scorer.score("December", "14 days annual leave")
        self.assertEqual(status, "fail")
    
    def test_keyword_match_all(self):
        scorer = Scorer(method="keyword")
        score, status, details = scorer.score("14 days annual leave per year", "14 days")
        self.assertEqual(score, 1.0)
        self.assertEqual(status, "pass")
    
    def test_keyword_match_partial(self):
        scorer = Scorer(method="keyword")
        score, status, details = scorer.score("14 days", "14 days annual leave")
        self.assertEqual(status, "partial")
        self.assertCountEqual(details.get("matched_keywords"), ["14", "days"])
    
    def test_keyword_match_none(self):
        scorer = Scorer(method="keyword")
        score, status, details = scorer.score("unrelated answer", "14 days annual leave")
        self.assertEqual(status, "fail")
    
    def test_keyword_empty_expected(self):
        scorer = Scorer(method="keyword")
        score, status, details = scorer.score("some response", "")
        self.assertEqual(score, 0.0)
    
    def test_hybrid_exact_path(self):
        score, status, details = self.scorer.score("14 days", "14 days")
        self.assertEqual(status, "pass")
        self.assertEqual(details["method"], "exact")
    
    def test_hybrid_keyword_path(self):
        score, status, details = self.scorer.score("14 days annual leave and extra words", "14 days annual leave")
        self.assertEqual(status, "pass")
        self.assertIn(details["method"], ("exact", "keyword"))
    
    def test_hybrid_fuzzy_path(self):
        score, status, details = self.scorer.score("14 days annual", "14 days")
        self.assertEqual(status, "pass")
    
    def test_hybrid_fail_path(self):
        score, status, details = self.scorer.score("December party", "probation period is 6 months")
        self.assertEqual(status, "fail")
    
    def test_calculate_pass_rate_mixed(self):
        results = [
            {"status": "pass"},
            {"status": "pass"},
            {"status": "fail"},
            {"status": "partial"}
        ]
        summary = calculate_pass_rate(results)
        self.assertEqual(summary["total"], 4)
        self.assertEqual(summary["passed"], 2)
        self.assertEqual(summary["failed"], 1)
        self.assertEqual(summary["partial"], 1)
        self.assertEqual(summary["pass_rate"], (2 + 0.5 * 1) / 4)
    
    def test_calculate_pass_rate_all_pass(self):
        results = [{"status": "pass"}, {"status": "pass"}]
        summary = calculate_pass_rate(results)
        self.assertEqual(summary["pass_rate"], 1.0)
    
    def test_calculate_pass_rate_all_fail(self):
        results = [{"status": "fail"}, {"status": "fail"}]
        summary = calculate_pass_rate(results)
        self.assertEqual(summary["pass_rate"], 0.0)
    
    def test_calculate_pass_rate_empty(self):
        summary = calculate_pass_rate([])
        self.assertEqual(summary["total"], 0)
        self.assertEqual(summary["pass_rate"], 0.0)
    
    def test_calculate_pass_rate_all_error(self):
        results = [{"status": "error"}, {"status": "error"}]
        summary = calculate_pass_rate(results)
        self.assertEqual(summary["total"], 2)
        self.assertEqual(summary["passed"], 0)
        self.assertEqual(summary["pass_rate"], 0.0)


class TestMockEndpointClient(unittest.TestCase):
    def test_fixed_mode(self):
        client = MockEndpointClient(mode="fixed")
        response = client.generate("What is the leave policy?")
        self.assertIn("choices", response)
        self.assertEqual(response["choices"][0]["message"]["content"], "14 days annual leave")
    
    def test_random_mode(self):
        client = MockEndpointClient(mode="random")
        responses = set()
        for _ in range(10):
            response = client.generate("What is the leave policy?")
            responses.add(response["choices"][0]["message"]["content"])
        self.assertGreater(len(responses), 1)
    
    def test_health_check(self):
        client = MockEndpointClient()
        self.assertTrue(client.health_check())


class TestGenerateSummary(unittest.TestCase):
    def test_generate_summary_includes_fields(self):
        results = [{"status": "pass"}, {"status": "fail"}]
        summary = generate_summary(results, "hybrid")
        self.assertIn("scoring_method", summary)
        self.assertIn("results", summary)
        self.assertIn("pass_rate", summary)
        self.assertEqual(summary["scoring_method"], "hybrid")
        self.assertEqual(len(summary["results"]), 2)


class TestBuildPrompt(unittest.TestCase):
    def test_build_prompt_no_context(self):
        prompt = build_prompt("What is the leave policy?")
        self.assertIn("What is the leave policy?", prompt)
        self.assertIn("You are a helpful assistant", prompt)
        self.assertNotIn("Context:", prompt)

    def test_build_prompt_with_context(self):
        context = "Employees get 14 days of annual leave."
        prompt = build_prompt("What is the leave policy?", context)
        self.assertIn("What is the leave policy?", prompt)
        self.assertIn("You are a helpful assistant", prompt)
        self.assertIn("Context:", prompt)
        self.assertIn(context, prompt)

    def test_build_prompt_empty_input(self):
        prompt = build_prompt("")
        self.assertIn("Question:", prompt)

    def test_build_prompt_special_chars(self):
        prompt = build_prompt("What's the policy? (urgent)")
        self.assertIn("What's the policy? (urgent)", prompt)


if __name__ == "__main__":
    unittest.main()