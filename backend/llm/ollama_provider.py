"""Ollama LLM provider — local Qwen3-8B/72B for meeting summarization.

Communicates with Ollama REST API (http://localhost:11434).
Supports streaming for progress updates.

File: backend/llm/ollama_provider.py
"""

from __future__ import annotations

from backend.llm.base import LLMProvider
from backend.config import settings

import structlog

logger = structlog.get_logger(__name__)


class OllamaProvider(LLMProvider):
    """Local LLM via Ollama (Qwen3-8B default, Qwen3-72B on DGX).

    Initialization:
        provider = OllamaProvider(model="qwen3:8b")
        result = await provider.summarize(transcript, system_prompt)
    """

    def __init__(
        self,
        model: str = "qwen3:8b",
        base_url: str = "",
        timeout: int = 300,
    ):
        self.model = model
        self.base_url = base_url or settings.ollama_base_url
        self.timeout = timeout

    async def summarize(self, transcript: str, system_prompt: str) -> str:
        """Generate meeting summary using local Ollama model."""
        import httpx

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": transcript},
            ],
            "stream": False,
            "options": {
                "temperature": 0.3,
                "num_predict": 4096,
            },
        }

        logger.info("Ollama summarizing", model=self.model, transcript_len=len(transcript))

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/api/chat",
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                raise RuntimeError(
                    f"Ollama model '{self.model}' not found. "
                    f"Please run: ollama pull {self.model}"
                ) from exc
            raise RuntimeError(f"Ollama HTTP error: {exc}") from exc
        except httpx.RequestError as exc:
            raise RuntimeError(
                f"Cannot connect to Ollama at {self.base_url}. "
                f"Is Ollama running? (run: ollama serve)"
            ) from exc

        content = data.get("message", {}).get("content", "")
        if not content:
            raise RuntimeError("Ollama returned empty response")

        logger.info("Ollama summarization complete", output_len=len(content))
        return content

    async def summarize_stream(self, transcript: str, system_prompt: str):
        """Streaming summarization — yields text chunks as they arrive."""
        import httpx

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": transcript},
            ],
            "stream": True,
            "options": {"temperature": 0.3, "num_predict": 4096},
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            async with client.stream("POST", f"{self.base_url}/api/chat", json=payload) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line:
                        continue
                    import json
                    try:
                        data = json.loads(line)
                        chunk = data.get("message", {}).get("content", "")
                        if chunk:
                            yield chunk
                        if data.get("done"):
                            break
                    except json.JSONDecodeError:
                        continue

    async def health_check(self) -> bool:
        """Check Ollama is running and the model is available."""
        import httpx
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.get(f"{self.base_url}/api/tags")
                response.raise_for_status()
                data = response.json()
                models = [m["name"] for m in data.get("models", [])]
                # Check if our model (or a variant) is loaded
                model_base = self.model.split(":")[0]
                available = any(model_base in m for m in models)
                if not available:
                    logger.warning(
                        "Ollama model not pulled",
                        model=self.model,
                        available_models=models,
                    )
                return available
        except httpx.RequestError as exc:
            logger.warning("Ollama health check failed - server not running", error=str(exc))
            return False
        except Exception as exc:
            logger.warning("Ollama health check failed", error=str(exc))
            return False
