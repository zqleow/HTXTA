import random
import time
from typing import Dict, Any


class MockEndpointClient:
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
        if self.mode == "fixed":
            return self._fixed_response(prompt)
        elif self.mode == "random":
            return self._random_response(prompt)
        else:
            return self._fixed_response(prompt)
    
    def _fixed_response(self, prompt: str) -> Dict[str, Any]:
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
        prompt = messages[-1]["content"] if messages else ""
        return self.generate(prompt)
    
    def health_check(self) -> bool:
        return True


class EndpointClient:
    def __init__(self, base_url: str):
        self.base_url = base_url
    
    def generate(self, prompt: str) -> Dict[str, Any]:
        import requests
        
        response = requests.post(
            f"{self.base_url}/v1/chat/completions",
            json={
                "model": "llama-3-8b",
                "messages": [
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": 500
            },
            timeout=30
        )
        response.raise_for_status()
        return response.json()
    
    def chat(self, messages: list) -> Dict[str, Any]:
        import requests
        
        response = requests.post(
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
    
    def health_check(self) -> bool:
        import requests
        try:
            response = requests.get(f"{self.base_url}/health", timeout=5)
            return response.status_code == 200
        except:
            return False