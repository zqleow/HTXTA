import json
import random
import time
from typing import Dict, Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry


class MockEndpointClient:
    """Returns pre-determined responses without making network calls.

    Two modes:
    - ``fixed``: returns the exact answer for each known question.
    - ``random``: picks a random answer from the response pool regardless of question.
    """

    def __init__(self, base_url: str = "http://localhost:8000", mode: str = "fixed"):
        self.base_url = base_url
        self.mode = mode
        self.responses = {
            "What is the leave policy?": "14 days annual leave",
            "Who approves travel claims?": "Direct manager",
            "How many days of remote work per week?": "2 days",
            "What is the probation period?": "6 months",
            "When is the annual function?": "December",
        }
    
    def generate(self, prompt: str) -> Dict[str, Any]:
        """Dispatch to fixed or random response handler based on ``self.mode``."""
        if self.mode == "fixed":
            return self._fixed_response(prompt)
        elif self.mode == "random":
            return self._random_response(prompt)
        else:
            return self._fixed_response(prompt)
    
    def _fixed_response(self, prompt: str) -> Dict[str, Any]:
        """Look up the expected answer for each question in ``self.responses``."""
        user_question = prompt.split("Question:")[-1].strip() if "Question:" in prompt else prompt
        
        response = self.responses.get(user_question, "No information available")
        
        return {
            "id": f"resp_{int(time.time() * 1000)}",
            "model": "mock-model",
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": response
                    },
                    "finish_reason": "stop"
                }
            ],
            "usage": {
                "prompt_tokens": len(prompt.split()),
                "completion_tokens": len(response.split()),
                "total_tokens": len(prompt.split()) + len(response.split())
            }
        }
    
    def _random_response(self, prompt: str) -> Dict[str, Any]:
        """Return a random response from the pool regardless of the question."""
        possible_responses = list(self.responses.values())
        response = random.choice(possible_responses)
        
        return {
            "id": f"resp_{int(time.time() * 1000)}",
            "model": "mock-model",
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": response
                    },
                    "finish_reason": "stop"
                }
            ],
            "usage": {
                "prompt_tokens": len(prompt.split()),
                "completion_tokens": len(response.split()),
                "total_tokens": len(prompt.split()) + len(response.split())
            }
        }
    
    def chat(self, messages: list) -> Dict[str, Any]:
        """Compatibility shim: extract content from the last message and delegate to ``generate``."""
        prompt = messages[-1]["content"] if messages else ""
        return self.generate(prompt)
    
    def health_check(self) -> bool:
        """Mock endpoint is always healthy."""
        return True


class EndpointClient:
    """HTTP client for OpenAI-compatible vLLM endpoints with retry support."""

    def __init__(self, base_url: str, system_prompt: str = ""):
        """Configure a requests Session with exponential-backoff retry.

        Retries on connection errors, timeouts, and HTTP 429/5xx up to 3 times
        with 1s-2s-4s backoff.
        """
        self.base_url = base_url
        self.system_prompt = system_prompt

        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["POST", "GET"],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session = requests.Session()
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

    def generate(self, question: str) -> Dict[str, Any]:
        """Send a single question and return the model's response.

        The system prompt (if any) is sent as a ``system`` role message, and the
        user question as a ``user`` role message, following the chat-completion
        format expected by vLLM / OpenAI-compatible APIs.
        """
        messages = []
        if self.system_prompt:
            messages.append({"role": "system", "content": self.system_prompt})
        messages.append({"role": "user", "content": question})

        try:
            response = self.session.post(
                f"{self.base_url}/v1/chat/completions",
                json={
                    "model": "llama-3-8b",
                    "messages": messages,
                    "max_tokens": 500
                },
                timeout=30
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.ConnectionError:
            return {"error": True, "error_type": "connection", "message": f"Could not connect to {self.base_url} after 3 retries"}
        except requests.exceptions.Timeout:
            return {"error": True, "error_type": "timeout", "message": "Request timed out after 30s and 3 retries"}
        except requests.exceptions.HTTPError as e:
            return {"error": True, "error_type": "http", "message": f"HTTP {response.status_code}: {e}"}
        except json.JSONDecodeError:
            return {"error": True, "error_type": "parse", "message": "Response was not valid JSON"}

    def chat(self, messages: list) -> Dict[str, Any]:
        """Send a pre-built message list (system+user+assistant) to the endpoint.

        Unlike ``generate``, this method does not wrap the messages — it passes
        them through as-is, useful for multi-turn conversations.
        """
        try:
            response = self.session.post(
                f"{self.base_url}/v1/chat/completions",
                json={
                    "model": "llama-3-8b",
                    "messages": messages,
                    "max_tokens": 500
                },
                timeout=30
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.ConnectionError:
            return {"error": True, "error_type": "connection", "message": f"Could not connect to {self.base_url} after 3 retries"}
        except requests.exceptions.Timeout:
            return {"error": True, "error_type": "timeout", "message": "Request timed out after 30s and 3 retries"}
        except requests.exceptions.HTTPError as e:
            return {"error": True, "error_type": "http", "message": f"HTTP {response.status_code}: {e}"}
        except json.JSONDecodeError:
            return {"error": True, "error_type": "parse", "message": "Response was not valid JSON"}

    def health_check(self) -> bool:
        """Ping the ``/health`` endpoint. Returns ``True`` on 200, ``False`` otherwise."""
        try:
            response = self.session.get(f"{self.base_url}/health", timeout=5)
            return response.status_code == 200
        except Exception:
            return False