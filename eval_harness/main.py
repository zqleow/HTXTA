#!/usr/bin/env python3
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from test_loader import TestLoader
from endpoint_client import MockEndpointClient, EndpointClient
from scorer import Scorer, generate_summary


SYSTEM_PROMPT = """You are a helpful assistant. Answer based only on the provided context."""


def build_prompt(question: str, context: str = "") -> str:
    """Construct the full prompt with system instructions and optional context."""
    if context:
        return f"{SYSTEM_PROMPT}\n\nContext:\n{context}\n\nQuestion: {question}"
    return f"{SYSTEM_PROMPT}\n\nQuestion: {question}"


def run_evaluation(test_file: str, endpoint_url: str, mock: bool, mode: str, scoring: str, verbose: bool) -> int:
    try:
        print(f"Loading test cases from: {test_file}")
        loader = TestLoader(test_file)
        test_cases = loader.load()
        loader.validate(test_cases)
        print(f"Loaded {len(test_cases)} test cases")
        
        if mock:
            print(f"Using mock endpoint (mode: {mode})")
            client = MockEndpointClient(endpoint_url, mode=mode)
        else:
            print(f"Using real endpoint: {endpoint_url}")
            client = EndpointClient(endpoint_url, system_prompt=SYSTEM_PROMPT)
        
        scorer = Scorer(method=scoring)
        results = []
        
        print(f"\nRunning evaluation...")
        for i, tc in enumerate(test_cases, 1):
            try:
                question = tc["input"]
                response_data = client.generate(question)
                
                if "error" in response_data:
                    raise RuntimeError(f"API error: {response_data['error_type']} - {response_data['message']}")
                
                actual_response = response_data["choices"][0]["message"]["content"]
                expected_response = tc["expected"]
                
                score, status, details = scorer.score(actual_response, expected_response)
                
                result = {
                    "id": tc["id"],
                    "input": tc["input"],
                    "expected": expected_response,
                    "actual": actual_response,
                    "score": score,
                    "status": status,
                    "details": details
                }
                results.append(result)
                
                if verbose:
                    print(f"  [{i}] {tc['id']}: {status} (score: {score:.2f})")
                    print(f"      Expected: {expected_response}")
                    print(f"      Actual:   {actual_response}")
                else:
                    print(f"  [{i}/{len(test_cases)}] {tc['id']}: {status}")
            
            except Exception as e:
                results.append({
                    "id": tc["id"],
                    "input": tc["input"],
                    "expected": tc["expected"],
                    "actual": None,
                    "score": 0.0,
                    "status": "error",
                    "details": {"error": str(e)}
                })
                print(f"  [{i}] {tc['id']}: ERROR - {e}")
        
        summary = generate_summary(results, scoring)
        
        print(f"\n{'='*60}")
        print(f"EVALUATION SUMMARY")
        print(f"{'='*60}")
        print(f"Total tests:    {summary['total']}")
        print(f"Passed:        {summary['passed']}")
        print(f"Partial:       {summary['partial']}")
        print(f"Failed:        {summary['failed']}")
        print(f"Pass rate:      {summary['pass_rate']*100:.1f}%")
        print(f"Scoring:       {summary['scoring_method']}")
        
        if summary['failed'] > 0:
            print(f"\nFailed tests:")
            for r in results:
                if r['status'] == 'fail':
                    print(f"  - {r['id']}: {r['details'].get('reason', 'mismatch')}")
        
        failures = [r for r in results if r['status'] == 'fail']
        error_tests = [r for r in results if r['status'] == 'error']
        
        if failures or error_tests:
            print(f"\nAnomalies (failed + errors): {len(failures) + len(error_tests)}")
        
        output_file = f"eval_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(output_file, 'w') as f:
            json.dump(summary, f, indent=2)
        print(f"\nResults saved to: {output_file}")
        
        return 0 if summary['pass_rate'] >= 0.8 else 1
    
    except FileNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 3
    except Exception as e:
        print(f"ERROR: Endpoint failure - {e}", file=sys.stderr)
        return 4


def main():
    """Parse CLI arguments and run the evaluation. Returns an exit code."""
    parser = argparse.ArgumentParser(
        description="LLM Evaluation Harness",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py --test-file data.jsonl --mock
  python main.py --test-file data.jsonl --endpoint http://localhost:8000
  python main.py --test-file data.jsonl --mock --scoring fuzzy --verbose
        """
    )
    
    parser.add_argument(
        "--test-file",
        type=str,
        default="test_data.jsonl",
        help="Path to JSONL test file"
    )
    parser.add_argument(
        "--endpoint",
        type=str,
        default="http://localhost:8000",
        help="Base URL for endpoint"
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Use mock endpoint instead of real"
    )
    parser.add_argument(
        "--mode",
        type=str,
        choices=["fixed", "random"],
        default="fixed",
        help="Mock response mode (default: fixed)"
    )
    parser.add_argument(
        "--scoring",
        type=str,
        choices=["exact", "fuzzy", "keyword", "hybrid"],
        default="hybrid",
        help="Scoring method (default: hybrid)"
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show verbose output"
    )
    
    args = parser.parse_args()
    
    if args.mock:
        return run_evaluation(
            args.test_file,
            args.endpoint,
            mock=True,
            mode=args.mode,
            scoring=args.scoring,
            verbose=args.verbose
        )
    else:
        return run_evaluation(
            args.test_file,
            args.endpoint,
            mock=False,
            mode="fixed",
            scoring=args.scoring,
            verbose=args.verbose
        )


if __name__ == "__main__":
    sys.exit(main())