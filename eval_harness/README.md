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

## Future Work / Further Improvements

### 1. LLM-as-judge scoring

Use an LLM to evaluate responses semantically rather than with string matching.

#### How It Works

Add a `--judge-endpoint` CLI flag pointing to an evaluator LLM (e.g., GPT-4, Claude, or a fine-tuned evaluator like Prometheus). The evaluator receives a structured prompt with the question, expected answer, and actual response, then returns a score.

#### Prompt Template

```
You are an expert evaluator of LLM responses. Given a question, an expected
answer, and an actual response, rate the actual response on three criteria:

1. Correctness (0.0-1.0): Does it contain the key information from the expected
   answer? Extra detail is fine; contradiction is not.
2. Completeness (0.0-1.0): Does it cover all required points?
3. Conciseness (0.0-1.0): Does it avoid irrelevant or redundant content?

Question: {question}
Expected answer: {expected}
Actual response: {actual}

Output ONLY a valid JSON object:
{{"score": <weighted average>, "correctness": <0.0-1.0>,
  "completeness": <0.0-1.0>, "conciseness": <0.0-1.0>,
  "reasoning": "<1-2 sentence justification>"}}
```

JSON output keeps the pipeline parseable. A `re.search(r'\{.*\}', text, re.DOTALL)` fallback handles markdown-wrapped responses. If parsing fails entirely, log the raw output and fall back to hybrid scoring.

#### Judge Calibration

A judge LLM has its own biases. Calibration ensures scores correlate with human judgment.

1. **Collect a human-annotated set** — 50-100 cases scored by 2-3 raters on the same rubric. Compute inter-rater reliability (Cohen's κ). Discard cases where humans disagree.
2. **Run the judge on the same set** — Compare judge vs human scores using:
   - Pearson/Spearman correlation (ranking consistency)
   - Mean absolute error (score accuracy)
   - Pass/fail confusion matrix at the threshold
3. **Adjust thresholds** — If the judge is systematically lenient (e.g., judge assigns 0.8 where humans assign 0.6), apply a calibration mapping.

**Periodic re-calibration:** Run the calibration set monthly against the latest judge model. Alert if correlation drops below 0.8.

#### Judge Bias Mitigation

| Bias | Mitigation |
|------|------------|
| **Self-enhancement** (prefers own outputs) | Use a different model as judge than the one being evaluated |
| **Position bias** (prefers first or last answer) | Test in both orders and average the scores |
| **Verbosity bias** (prefers longer answers) | Add conciseness criterion; constrain judge `max_tokens` |
| **Rubric overfitting** (always gives 1.0) | Include trap cases (plausible-sounding but wrong answers) in calibration |
| **Score anchoring** (defaults to mid-range) | Few-shot prompt with examples at 0.2, 0.5, 0.8, 1.0 |

For high-stakes evaluations, run a multi-judge ensemble (3 models) and take the median. Flag cases where judges disagree by >0.3 for human review.

#### Integration Into the Harness

```python
class JudgeScorer:
    def __init__(self, judge_endpoint: str, model: str = "gpt-4"):
        self.client = EndpointClient(judge_endpoint)
        self.model = model

    def score(self, response, expected, question="") -> Tuple[float, str, Dict]:
        # Build prompt → call judge → parse JSON → return (score, status, details)
```

- New CLI flag `--judge-endpoint` activates judge scoring (overrides `--scoring` to `judge`).
- `Scorer.score()` dispatches to `JudgeScorer` when method is `"judge"`, passing `question` through.
- Cache judge results by `(question, response)` hash in a local JSON/SQLite store to avoid redundant calls.

#### Tradeoffs vs String-Based Scoring

| Aspect | String-based | LLM-as-judge |
|--------|-------------|--------------|
| Speed | ~1ms per test | ~1-5s per test |
| Cost | Free | API cost or GPU time |
| Semantic understanding | None | High |
| Bias | None | Multiple types to mitigate |
| Reliability | Deterministic | Probabilistic (needs calibration) |
| Best for | Factual QA, short answers | Open-ended, reasoning, creative tasks |

**Recommended approach:** Run string-based scoring as the fast default, and enable LLM-as-judge via `--judge-endpoint` for deeper evaluation. Production pipelines run both and flag disagreements.

---

### 2. Batch processing

Async parallel requests to the endpoint to reduce evaluation time when running hundreds of test cases. Use `concurrent.futures.ThreadPoolExecutor` or `asyncio` with `aiohttp`.

### 3. Report generation

Export results as HTML or PDF with pass/fail breakdowns, per-metric charts, and per-test-case details.

### 4. Threshold configuration

Make the pass/fail threshold (`0.8` in `run_evaluation`) configurable via `--threshold`. Different use cases may require stricter (compliance) or looser (creative) bars.

### 5. Metrics logging

Log results as structured JSON lines to a file for CI/CD trend tracking (e.g., "did this PR improve or regress our eval scores?").