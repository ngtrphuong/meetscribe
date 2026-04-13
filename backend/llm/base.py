"""LLM Provider abstract interface.

All LLM providers (Ollama, Claude, OpenAI, Gemini, MiniMax, Qwen Cloud)
MUST implement this interface.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class LLMProvider(ABC):
    """Abstract base for all LLM summarization providers."""

    @abstractmethod
    async def summarize(self, transcript: str, system_prompt: str) -> str:
        """Generate summary from transcript using system prompt template."""

    @abstractmethod
    async def health_check(self) -> bool:
        """Verify provider is reachable and model is loaded."""
