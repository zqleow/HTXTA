# LLM Evaluation Harness

A lightweight CLI tool for evaluating LLM responses against expected outputs.

## What It Does

- Loads test cases from a JSONL file
- Runs each test case against an endpoint (mock or real)
- Scores responses using configurable scoring methods
- Outputs a structured summary (pass rate, failures, anomalies)

## How to Run

```bash
# Using mock endpoint (default - returns fixed responses)
python main.py --test-file test_data.jsonl --mock

# Using real endpoint
python main.py --test-file test_data.jsonl --endpoint http://localhost:8000

# With verbose output
python main.py --test-file test_data.jsonl --mock --verbose

# With specific scoring method
python main.py --test-file test_data.jsonl --mock --scoring fuzzy
```

## Test Data Format

JSONL file with one JSON object per line:

```json
{"id": "q1", "input": "What is the leave policy?", "expected": "14 days annual leave"}
{"id": "q2", "input": "Who approves travel claims?", "expected": "Direct manager"}
```

Required fields:
- `id`: Unique test identifier
- `input`: User question
- `expected`: Expected answer

## Scoring Methods

| Method | Description | Use Case |
|--------|-------------|----------|
| `exact` | Exact string match | Precise answers |
| `fuzzy` | String similarity (SequenceMatcher) | Slight variations |
| `keyword` | Keyword overlap | Partial matches |
| `hybrid` | Combination of all above | Best overall (default) |

## Options

| Option | Description |
|--------|-------------|
| `--test-file` | Path to JSONL test file (default: test_data.jsonl) |
| `--endpoint` | Base URL for endpoint (default: http://localhost:8000) |
| `--mock` | Use mock endpoint instead of real |
| `--mode` | Mock response mode: `fixed` or `random` |
| `--scoring` | Scoring method: `exact`, `fuzzy`, `keyword`, or `hybrid` |
| `--verbose`, `-v` | Show verbose output |

## Output

The tool outputs:

- Pass/fail for each test case
- Pass rate percentage
- Failed tests with reasons
- Any anomalies (errors)
- Results saved to JSON file

## Unit Tests

Run tests with:

```bash
python -m pytest tests/test_core.py -v
```

## Error Handling

The tool handles:
- Missing test file → Error message + exit code 2
- Malformed JSON in test file → Error with line number + exit code 3
- Endpoint failures → Error message + exit code 4
- Invalid test data fields → Validation error + exit code 3

## Architecture

```
test_data.jsonl
       ↓
TestLoader (parse JSONL)
       ↓
EndpointClient (mock or real)
       ↓
Scorer (evaluate response)
       ↓
Summary Report
```

## What I'd Add With More Time

1. **LLM-as-judge scoring**: Use an LLM to evaluate responses semantically
2. **Batch processing**: Async parallel requests
3. **Report generation**: HTML/PDF reports
4. **Threshold configuration**: Configurable pass/fail threshold
5. **Metrics logging**: Log to file for CI/CD integration