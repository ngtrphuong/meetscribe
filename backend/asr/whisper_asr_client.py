"""whisper-asr-webservice REST client.

Connects to the Docker whisper-asr-webservice (port 9000).
Used as an alternative to running faster-whisper in-process.

Docker service: onerahmet/openai-whisper-asr-webservice:latest-gpu

File: backend/asr/whisper_asr_client.py
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


class WhisperASRClient(ASREngine):
    """REST client for whisper-asr-webservice microservice.

    Initialization config keys:
        language: str   (default: "vi")
        task: str       "transcribe" or "translate" (default: "transcribe")
        output: str     "json" (default)
    """

    def __init__(self):
        self._config: dict = {}
        self._base_url: str = ""
        self._initialized = False

    async def initialize(self, config: dict) -> None:
        self._config = config
        self._base_url = settings.whisper_asr_url
        self._initialized = True
        logger.info("WhisperASR client ready", url=self._base_url)

    async def transcribe_stream(
        self, audio_chunks: AsyncIterator[bytes]
    ) -> AsyncIterator[TranscriptSegment]:
        """Buffer 5s windows and send to REST endpoint."""
        buffer = bytearray()
        window_bytes = SAMPLE_RATE * 2 * 5

        async for chunk in audio_chunks:
            buffer.extend(chunk)
            if len(buffer) >= window_bytes:
                segs = await self._post_audio(bytes(buffer))
                buffer.clear()
                for s in segs:
                    yield s

        if buffer:
            for s in await self._post_audio(bytes(buffer)):
                yield s

    async def transcribe_file(
        self, file_path: str, hotwords: Optional[list[str]] = None
    ) -> list[TranscriptSegment]:
        with open(file_path, "rb") as f:
            return await self._post_audio_bytes(f.read(), filename=file_path)

    async def _post_audio(self, pcm: bytes) -> list[TranscriptSegment]:
        """Wrap PCM in WAV and POST to whisper-asr-webservice."""
        wav_buf = io.BytesIO()
        with wave.open(wav_buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(pcm)
        return await self._post_audio_bytes(wav_buf.getvalue(), "audio.wav")

    async def _post_audio_bytes(self, audio_bytes: bytes, filename: str = "audio.wav") -> list[TranscriptSegment]:
        import httpx

        language = self._config.get("language", "vi")
        task = self._config.get("task", "transcribe")

        url = f"{self._base_url}/asr"
        params = {"output": "json", "language": language, "task": task}

        try:
            async with httpx.AsyncClient(timeout=60) as client:
                response = await client.post(
                    url,
                    params=params,
                    files={"audio_file": (filename, audio_bytes, "audio/wav")},
                )
                response.raise_for_status()
                data = response.json()

            text = data.get("text", "").strip()
            if not text:
                return []

            return [TranscriptSegment(
                text=text,
                start_time=0.0,
                end_time=0.0,
                confidence=0.9,
                language=language,
                is_final=True,
                source="live",
            )]
        except Exception as exc:
            logger.error("whisper-asr-webservice error", error=str(exc))
            return []

    async def shutdown(self) -> None:
        self._initialized = False

    @property
    def capabilities(self) -> dict:
        return {
            "streaming": True,
            "languages": ["vi", "en", "auto"],
            "gpu_required": False,
            "gpu_vram_mb": 0,
            "has_diarization": False,
            "has_timestamps": False,
            "has_punctuation": True,
            "model_name": "whisper-asr-webservice",
        }
