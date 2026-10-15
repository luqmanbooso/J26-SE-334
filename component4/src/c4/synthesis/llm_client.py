"""Provider-neutral language-model client interface."""

from __future__ import annotations

from typing import Protocol


class LLMClient(Protocol):
    """Client that generates text from a synthesis prompt."""

    def generate(self, prompt: str) -> str:
        """Generate a model response for a prompt."""
