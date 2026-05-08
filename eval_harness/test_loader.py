import json
from pathlib import Path
from typing import List, Dict, Any


class TestLoader:
    """Parses and validates JSONL test files containing LLM evaluation cases.

    Each line must be a JSON object with ``id``, ``input``, and ``expected`` keys.
    """

    def __init__(self, file_path: str):
        self.file_path = Path(file_path)
    
    def load(self) -> List[Dict[str, Any]]:
        """Read the JSONL file and return a list of test-case dicts.

        Raises ``FileNotFoundError`` if the file does not exist,
        ``ValueError`` if any line has invalid JSON or missing required fields.
        """
        if not self.file_path.exists():
            raise FileNotFoundError(f"Test file not found: {self.file_path}")
        
        test_cases = []
        with open(self.file_path, 'r') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    test_case = json.loads(line)
                    if not all(k in test_case for k in ['id', 'input', 'expected']):
                        raise ValueError(f"Missing required fields in line {line_num}")
                    test_cases.append(test_case)
                except json.JSONDecodeError as e:
                    raise ValueError(f"Invalid JSON in line {line_num}: {e}")
        
        if not test_cases:
            raise ValueError("No valid test cases found")
        
        return test_cases
    
    def validate(self, test_cases: List[Dict[str, Any]]) -> bool:
        """Check that every test case has string-typed ``id``, ``input``, and ``expected``."""
        for tc in test_cases:
            if not isinstance(tc.get('id'), str):
                raise ValueError(f"Invalid id type: {type(tc.get('id'))}")
            if not isinstance(tc.get('input'), str):
                raise ValueError(f"Invalid input type: {type(tc.get('input'))}")
            if not isinstance(tc.get('expected'), str):
                raise ValueError(f"Invalid expected type: {type(tc.get('expected'))}")
        return True