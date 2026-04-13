"""GASR (Google SODA) ASR engine — CPU-only offline fallback.

Uses Google's SODA offline ASR engine via the gasr submodule.
No GPU required. Lower accuracy than Parakeet but works on CPU-only systems.

Submodule: engines/gasr/ (ngtrphuong/gasr)
Setup: cd engines/gasr && python prep.py -s -l "en-us"

File: backend/asr/gasr_engine.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import AsyncIterator, Optional

import structlog

from backend.asr.base import ASREngine, TranscriptSegment

logger = structlog.get_logger(__name__)

_GASR_PATH = Path(__file__).parent.parent.parent / "engines" / "gasr"
SAMPLE_RATE = 16_000


class GASREngine(ASREngine):
    """CPU-only ASR via Google SODA offline engine (gasr submodule).

    Initialization config keys:
        language: str  (default: "en-us")
        model_dir: str (default: engines/gasr/models)
    """

    def __init__(self):
        self._recognizer = None
        self._config: dict = {}
        self._initialized = False

    async def initialize(self, config: dict) -> None:
        self._config = config

        if str(_GASR_PATH) not in sys.path:
            sys.path.insert(0, str(_GASR_PATH))

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._load)
        self._initialized = True

    def _load(self) -> None:
        try:
            import gasr
            lang = self._config.get("language", "en-us")
            model_dir = self._config.get("model_dir", str(_GASR_PATH / "models"))
            self._recognizer = gasr.Recognizer(language=lang, model_dir=model_dir)
            logger.info("GASR loaded", language=lang)
        except ImportError:
            raise ImportError(
                "gasr submodule not available. "
                "Run: cd engines/gasr && python prep.py -s -l 'en-us'"
            )

    async def transcribe_stream(
        self, audio_chunks: AsyncIterator[bytes]
    ) -> AsyncIterator[TranscriptSegment]:
        if not self._initialized or not self._recognizer:
            raise RuntimeError("GASR not initialized")

        async for chunk in audio_chunks:
            loop = asyncio.get_event_loop()
            text = await loop.run_in_executor(None, self._recognizer.process, chunk)
            if text:
                yield TranscriptSegment(
                    text=text,
                    start_time=0.0,
                    end_time=len(chunk) / (SAMPLE_RATE * 2),
                    confidence=0.8,
                    language=self._config.get("language", "en"),
                    is_final=True,
                    source="live",
                )

    async def transcribe_file(
        self, file_path: str, hotwords: Optional[list[str]] = None
    ) -> list[TranscriptSegment]:
        import wave

        with wave.open(file_path, "rb") as wf:
            pcm = wf.readframes(wf.getnframes())
            framerate = wf.getframerate()

        # Process in 1s chunks
        chunk_size = framerate * 2    # 1s at 16kHz int16
        segments = []
        offset = 0.0

        for i in range(0, len(pcm), chunk_size):
            chunk = pcm[i:i + chunk_size]
            loop = asyncio.get_event_loop()
            text = await loop.run_in_executor(None, self._recognizer.process, chunk)
            if text:
                segments.append(TranscriptSegment(
                    text=text,
                    start_time=offset,
                    end_time=offset + len(chunk) / (framerate * 2),
                    confidence=0.8,
                    language=self._config.get("language", "en"),
                    is_final=True,
                    source="post",
                ))
            offset += len(chunk) / (framerate * 2)

        return segments

    async def shutdown(self) -> None:
        self._recognizer = None
        self._initialized = False

    @property
    def capabilities(self) -> dict:
        return {
            "streaming": True,
            "languages": ["en-us", "vi-vn"],
            "gpu_required": False,
            "gpu_vram_mb": 0,
            "has_diarization": False,
            "has_timestamps": False,
            "has_punctuation": False,
            "model_name": "google-soda-offline",
        }
