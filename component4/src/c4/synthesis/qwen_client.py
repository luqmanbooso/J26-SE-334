"""Ollama client for local Qwen3 inference."""

from __future__ import annotations

import json
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class QwenClientError(RuntimeError):
    """Raised when Ollama cannot return a valid generation response."""


@dataclass(frozen=True)
class OllamaQwenClient:
    """Small standard-library client for Ollama's generate endpoint."""

    base_url: str = "http://127.0.0.1:11434"
    model: str = "qwen3:8b"
    seed: int = 42
    num_ctx: int = 8192
    num_predict: int = 1024
    temperature: float = 0.0
    think: bool = False
    json_mode: bool = True
    timeout_seconds: float = 120.0

    def generate(self, prompt: str) -> str:
        """Generate one non-streaming response from the configured model."""
        request_body: dict[str, object] = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "think": self.think,
            "options": {
                "temperature": self.temperature,
                "seed": self.seed,
                "num_ctx": self.num_ctx,
                "num_predict": self.num_predict,
            },
        }
        if self.json_mode:
            request_body["format"] = "json"
        request = Request(
            f"{self.base_url.rstrip('/')}/api/generate",
            data=json.dumps(request_body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                body = json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError) as error:
            raise QwenClientError("Ollama generation request failed") from error
        result = body.get("response")
        if not isinstance(result, str) or not result.strip():
            raise QwenClientError("Ollama response did not contain generated text")
        return result
