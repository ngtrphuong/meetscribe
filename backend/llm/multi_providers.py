"""Multi-provider LLM clients for MeetScribe summarization.

Supports: Ollama (local), Claude, OpenAI, Google Gemini, MiniMax, Alibaba Qwen.
All implement the same LLMProvider interface from backend/llm/base.py.
"""

from __future__ import annotations

from backend.llm.base import LLMProvider


class GeminiProvider(LLMProvider):
    """Google Gemini API for summarization."""

    def __init__(self, api_key: str, model: str = "gemini-2.5-flash"):
        self.api_key = api_key
        self.model = model

    async def summarize(self, transcript: str, system_prompt: str) -> str:
        from google import genai

        client = genai.Client(api_key=self.api_key)
        response = await client.aio.models.generate_content(
            model=self.model,
            contents=f"{system_prompt}\n\nTRANSCRIPT:\n{transcript}",
        )
        return response.text

    async def health_check(self) -> bool:
        try:
            from google import genai
            client = genai.Client(api_key=self.api_key)
            return True
        except Exception:
            return False


class MiniMaxProvider(LLMProvider):
    """MiniMax API for summarization (strong multilingual, Chinese/Vietnamese)."""

    def __init__(self, api_key: str, group_id: str, model: str = "MiniMax-M2.5"):
        self.api_key = api_key
        self.group_id = group_id
        self.model = model

    async def summarize(self, transcript: str, system_prompt: str) -> str:
        import httpx

        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(
                f"https://api.minimax.chat/v1/text/chatcompletion_v2",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": transcript},
                    ],
                    "max_tokens": 4096,
                    "temperature": 0.3,
                },
            )
            data = response.json()
            return data["choices"][0]["message"]["content"]

    async def health_check(self) -> bool:
        return bool(self.api_key and self.group_id)


class QwenCloudProvider(LLMProvider):
    """Alibaba Qwen (DashScope) API for summarization.

    Excellent for Vietnamese + Chinese + English mixed content.
    Uses OpenAI-compatible endpoint.
    """

    def __init__(self, api_key: str, model: str = "qwen-max"):
        self.api_key = api_key
        self.model = model

    async def summarize(self, transcript: str, system_prompt: str) -> str:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(
            api_key=self.api_key,
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        )
        response = await client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": transcript},
            ],
            max_tokens=4096,
            temperature=0.3,
        )
        return response.choices[0].message.content

    async def health_check(self) -> bool:
        return bool(self.api_key)


class OpenAIProvider(LLMProvider):
    """OpenAI GPT-4.1 for summarization."""

    def __init__(self, api_key: str, model: str = "gpt-4.1"):
        self.api_key = api_key
        self.model = model

    async def summarize(self, transcript: str, system_prompt: str) -> str:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=self.api_key)
        response = await client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": transcript},
            ],
            max_tokens=4096,
            temperature=0.3,
        )
        return response.choices[0].message.content

    async def health_check(self) -> bool:
        return bool(self.api_key)
