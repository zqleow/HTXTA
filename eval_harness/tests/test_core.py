import unittest
import json
import tempfile
import os
from pathlib import Path

from test_loader import TestLoader
from scorer import Scorer, calculate_pass_rate
from endpoint_client import MockEndpointClient


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
    
    def test_fuzzy_match(self):
        scorer = Scorer(method="fuzzy")
        score, status, details = scorer.score("14 days annual leave", "14 days")
        self.assertGreater(score, 0.5)
    
    def test_keyword_match(self):
        scorer = Scorer(method="keyword")
        score, status, details = scorer.score("14 days annual leave per year", "14 days")
        self.assertGreater(score, 0.0)
    
    def test_hybrid_scoring(self):
        score, status, details = self.scorer.score("14 days", "14 days")
        self.assertEqual(status, "pass")
    
    def test_calculate_pass_rate(self):
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


if __name__ == "__main__":
    unittest.main()