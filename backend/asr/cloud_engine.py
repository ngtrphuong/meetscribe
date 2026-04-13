"""Cloud ASR engine — Groq / OpenAI Whisper API.

File: backend/asr/cloud_engine.py
"""

from __future__ import annotations

import asyncio
import io
import wave
from typing import AsyncIterator, Optional

import structlog

from backend.asr.base import ASREngine, TranscriptSegment
from backend.config import settings

logger = structlog.get_logger(__name__)

SAMPLE_RATE = 16_000


class CloudASREngine(ASREngine):
    """Cloud ASR via Groq (fast) or OpenAI Whisper API (fallback).

    Initialization config keys:
        provider: str   "groq" or "openai" (default: "groq")
        language: str   ISO 639-1 (default: "vi")
    """

    def __init__(self):
        self._config: dict = {}
        self._initialized = False

    async def initialize(self, config: dict) -> None:
        self._config = config
        provider = config.get("provider", "groq")
        api_key = (
            settings.groq_api_key if provider == "groq" else settings.openai_api_key
        )
        if not api_key:
            raise RuntimeError(f"No API key set for cloud provider '{provider}'")
        self._initialized = True
        logger.info("Cloud ASR engine ready", provider=provider)

    async def transcribe_stream(
        self, audio_chunks: AsyncIterator[bytes]
    ) -> AsyncIterator[TranscriptSegment]:
        """Buffer 10s windows and submit to cloud API."""
        buffer = bytearray()
        window_bytes = SAMPLE_RATE * 2 * 10

        async for chunk in audio_chunks:
            buffer.extend(chunk)
            if len(buffer) >= window_bytes:
                segs = await self._transcribe_pcm(bytes(buffer))
                buffer.clear()
                for s in segs:
                    yield s

        if buffer:
            for s in await self._transcribe_pcm(bytes(buffer)):
                yield s

    async def transcribe_file(
        self, file_path: str, hotwords: Optional[list[str]] = None
    ) -> list[TranscriptSegment]:
        provider = self._config.get("provider", "groq")
        language = self._config.get("language", "vi")

        with open(file_path, "rb") as f:
            audio_bytes = f.read()

        return await self._submit_to_api(audio_bytes, provider, language, file_path)

    async def _transcribe_pcm(self, pcm: bytes) -> list[TranscriptSegment]:
        # Wrap PCM in WAV container
        wav_buf = io.BytesIO()
        with wave.open(wav_buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(pcm)
        wav_bytes = wav_buf.getvalue()

        provider = self._config.get("provider", "groq")
        language = self._config.get("language", "vi")
        return await self._submit_to_api(wav_bytes, provider, language, "audio.wav")

    async def _submit_to_api(
        self, audio_bytes: bytes, provider: str, language: str, filename: str
    ) -> list[TranscriptSegment]:
        import httpx

        if provider == "groq":
            url = "https://api.groq.com/openai/v1/audio/transcriptions"
            api_key = settings.groq_api_key
            model = "whisper-large-v3"
        else:
            url = "https://api.openai.com/v1/audio/transcriptions"
            api_key = settings.openai_api_key
            model = "whisper-1"

        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                url,
                headers={"Authorization": f"Bearer {api_key}"},
                files={"file": (filename, audio_bytes, "audio/wav")},
                data={"model": model, "language": language, "response_format": "verbose_json"},
            )
            response.raise_for_status()
            data = response.json()

        segments = []
        for seg in data.get("segments", [{"text": data.get("text", ""), "start": 0, "end": 0}]):
            text = seg.get("text", "").strip()
            if text:
                segments.append(TranscriptSegment(
                    text=text,
                    start_time=seg.get("start", 0.0),
                    end_time=seg.get("end", 0.0),
                    confidence=seg.get("avg_logprob", 0.9),
                    language=language,
                    is_final=True,
                    source="live",
                ))
        return segments

    async def shutdown(self) -> None:
        self._initialized = False

    @property
    def capabilities(self) -> dict:
        return {
            "streaming": True,
            "languages": ["vi", "en", "zh", "fr", "de"],
            "gpu_required": False,
            "gpu_vram_mb": 0,
            "has_diarization": False,
            "has_timestamps": True,
            "has_punctuation": True,
            "model_name": f"cloud-whisper-{self._config.get('provider', 'groq')}",
        }
