"""PhoWhisper Vietnamese ASR — fallback when Parakeet is unavailable.

VinAI PhoWhisper-large — fine-tuned Whisper for Vietnamese.
Falls back to this if Parakeet is unavailable.

File: backend/asr/phowhisper_engine.py
"""

from __future__ import annotations

import asyncio
import io
import wave
from typing import AsyncIterator, Optional

import structlog

from backend.asr.base import ASREngine, TranscriptSegment

logger = structlog.get_logger(__name__)

MODEL_NAME = "vinai/PhoWhisper-large"
SAMPLE_RATE = 16_000


class PhoWhisperEngine(ASREngine):
    """Vietnamese ASR via VinAI PhoWhisper-large (transformers backend).

    Initialization config keys:
        model_name: str  (default: "vinai/PhoWhisper-large")
        device: str      (default: "cuda")
    """

    def __init__(self):
        self._pipe = None
        self._config: dict = {}
        self._initialized = False

    async def initialize(self, config: dict) -> None:
        self._config = config
        model_name = config.get("model_name", MODEL_NAME)
        device = config.get("device", "cuda")

        logger.info("Loading PhoWhisper", model=model_name)

        loop = asyncio.get_event_loop()
        self._pipe = await loop.run_in_executor(
            None, self._load_model, model_name, device
        )
        self._initialized = True
        logger.info("PhoWhisper ready")

    def _load_model(self, model_name: str, device: str):
        from transformers import pipeline
        return pipeline(
            "automatic-speech-recognition",
            model=model_name,
            device=0 if device == "cuda" else -1,
            chunk_length_s=30,
            stride_length_s=5,
        )

    async def transcribe_stream(
        self, audio_chunks: AsyncIterator[bytes]
    ) -> AsyncIterator[TranscriptSegment]:
        buffer = bytearray()
        window_bytes = SAMPLE_RATE * 2 * 5   # 5s windows

        async for chunk in audio_chunks:
            buffer.extend(chunk)
            if len(buffer) >= window_bytes:
                segs = await self._transcribe_pcm(bytes(buffer))
                buffer.clear()
                for seg in segs:
                    yield seg

        if buffer:
            for seg in await self._transcribe_pcm(bytes(buffer)):
                yield seg

    async def transcribe_file(
        self, file_path: str, hotwords: Optional[list[str]] = None
    ) -> list[TranscriptSegment]:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._run_file, file_path)

    def _run_file(self, file_path: str) -> list[TranscriptSegment]:
        result = self._pipe(file_path, return_timestamps=True)
        segments = []

        # Handle multiple chunks with timestamps
        chunks_data = result.get("chunks", [])
        if not chunks_data:
            # Fallback: use full text with estimated duration
            text = result.get("text", "").strip()
            if text:
                segments.append(TranscriptSegment(
                    text=text,
                    start_time=0.0,
                    end_time=0.0,  # Will be estimated by caller
                    confidence=0.85,
                    language="vi",
                    is_final=True,
                    source="post",
                ))
        else:
            for chunk in chunks_data:
                text = chunk.get("text", "").strip()
                if not text:
                    continue
                timestamp = chunk.get("timestamp")
                if timestamp and isinstance(timestamp, (list, tuple)) and len(timestamp) == 2:
                    start = float(timestamp[0]) if timestamp[0] is not None else 0.0
                    end = float(timestamp[1]) if timestamp[1] is not None else 0.0
                else:
                    start, end = 0.0, 0.0
                segments.append(TranscriptSegment(
                    text=text,
                    start_time=start,
                    end_time=end,
                    confidence=0.85,
                    language="vi",
                    is_final=True,
                    source="post",
                ))
        return segments

    async def _transcribe_pcm(self, pcm: bytes) -> list[TranscriptSegment]:
        import numpy as np
        audio = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, self._pipe, {"array": audio, "sampling_rate": SAMPLE_RATE})

        text = result.get("text", "").strip()
        if not text:
            return []

        duration = len(pcm) / (SAMPLE_RATE * 2)
        return [TranscriptSegment(
            text=text,
            start_time=0.0,
            end_time=duration,
            confidence=0.85,
            language="vi",
            is_final=True,
            source="live",
        )]

    async def shutdown(self) -> None:
        self._pipe = None
        self._initialized = False
        logger.info("PhoWhisper unloaded")

    @property
    def capabilities(self) -> dict:
        return {
            "streaming": True,
            "languages": ["vi"],
            "gpu_required": False,
            "gpu_vram_mb": 3000,
            "has_diarization": False,
            "has_timestamps": True,
            "has_punctuation": True,
            "model_name": self._config.get("model_name", MODEL_NAME),
        }
