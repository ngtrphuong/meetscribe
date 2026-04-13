"""Claude (Anthropic) LLM provider — highest quality cloud summarization.

Uses Claude Sonnet 4 (claude-sonnet-4-6) for meeting summaries.
Requires MEETSCRIBE_ANTHROPIC_API_KEY environment variable.

File: backend/llm/claude_provider.py
"""

from __future__ import annotations

from backend.llm.base import LLMProvider
from backend.config import settings

import structlog

logger = structlog.get_logger(__name__)

DEFAULT_MODEL = "claude-sonnet-4-6"
DEFAULT_MAX_TOKENS = 4096


class ClaudeProvider(LLMProvider):
    """Cloud LLM via Anthropic Claude API.

    Initialization:
        provider = ClaudeProvider()   # reads API key from settings
        result = await provider.summarize(transcript, system_prompt)
    """

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        api_key: str = "",
    ):
        self.model = model
        self.max_tokens = max_tokens
        self.api_key = api_key or settings.anthropic_api_key

    async def summarize(self, transcript: str, system_prompt: str) -> str:
        """Generate meeting summary via Claude API."""
        if not self.api_key:
            raise RuntimeError(
                "Anthropic API key not set. Set MEETSCRIBE_ANTHROPIC_API_KEY."
            )

        from anthropic import AsyncAnthropic

        client = AsyncAnthropic(api_key=self.api_key)

        logger.info("Claude summarizing", model=self.model, transcript_len=len(transcript))

        message = await client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=system_prompt,
            messages=[
                {"role": "user", "content": transcript},
            ],
            temperature=0.3,
        )

        content = message.content[0].text if message.content else ""
        logger.info("Claude summarization complete", output_len=len(content))
        return content

    async def summarize_stream(self, transcript: str, system_prompt: str):
        """Streaming summarization via Claude API."""
        if not self.api_key:
            raise RuntimeError("Anthropic API key not set.")

        from anthropic import AsyncAnthropic

        client = AsyncAnthropic(api_key=self.api_key)

        async with client.messages.stream(
            model=self.model,
            max_tokens=self.max_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": transcript}],
            temperature=0.3,
        ) as stream:
            async for text in stream.text_stream:
                yield text

    async def health_check(self) -> bool:
        """Verify the API key is set and the API is reachable."""
        if not self.api_key:
            return False
        try:
            from anthropic import AsyncAnthropic
            client = AsyncAnthropic(api_key=self.api_key)
            # Lightweight check — list models
            await client.models.list()
            return True
        except Exception as exc:
            logger.warning("Claude health check failed", error=str(exc))
            return False
