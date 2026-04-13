"""NVIDIA Maxine audio preprocessing — AEC + Background Noise Removal.

NVIDIA Maxine provides:
  - Acoustic Echo Cancellation (AEC): removes speaker feedback
  - Background Noise Removal (BNR): suppresses HVAC, keyboard, traffic

GPU VRAM: ~0.5GB.
Falls back to passthrough (no-op) if Maxine SDK is not installed.

File: backend/audio/maxine_preprocessor.py
"""

from __future__ import annotations

import asyncio
from typing import AsyncIterator

import structlog

logger = structlog.get_logger(__name__)

SAMPLE_RATE = 16_000
CHUNK_SAMPLES = 1600    # 100ms at 16kHz


class MaxinePreprocessor:
    """NVIDIA Maxine AEC + BNR preprocessing.

    If Maxine SDK (nvidia-maxine) is not installed or GPU is unavailable,
    this is a transparent passthrough — no quality degradation.

    Usage:
        preprocessor = MaxinePreprocessor()
        await preprocessor.initialize()
        async for clean_chunk in preprocessor.process(raw_stream):
            yield clean_chunk
    """

    def __init__(self, enable_aec: bool = True, enable_bnr: bool = True):
        self.enable_aec = enable_aec
        self.enable_bnr = enable_bnr
        self._maxine_available = False
        self._aec_session = None
        self._bnr_session = None

    async def initialize(self) -> None:
        """Attempt to initialise Maxine SDK sessions."""
        try:
            import nvidia.maxine as maxine
            self._aec_session = maxine.AudioEffectsSession(effects=["AEC"])
            self._bnr_session = maxine.AudioEffectsSession(effects=["BNR"])
            self._maxine_available = True
            logger.info("NVIDIA Maxine AEC+BNR initialised")
        except ImportError:
            logger.info("NVIDIA Maxine SDK not installed — using passthrough (no AEC/BNR)")
        except Exception as exc:
            logger.warning("Maxine init failed, using passthrough", error=str(exc))

    async def process(
        self, audio_stream: AsyncIterator[bytes]
    ) -> AsyncIterator[bytes]:
        """Process audio chunks through AEC+BNR (or passthrough)."""
        async for chunk in audio_stream:
            if not self._maxine_available:
                yield chunk
                continue

            loop = asyncio.get_event_loop()
            processed = await loop.run_in_executor(None, self._process_chunk, chunk)
            yield processed

    def _process_chunk(self, chunk: bytes) -> bytes:
        """Run Maxine effects on a PCM chunk (in thread executor)."""
        try:
            import numpy as np
            audio = np.frombuffer(chunk, dtype=np.int16).astype(np.float32) / 32768.0

            if self.enable_bnr and self._bnr_session:
                audio = self._bnr_session.process(audio)
            if self.enable_aec and self._aec_session:
                audio = self._aec_session.process(audio)

            return (audio * 32768.0).clip(-32768, 32767).astype("int16").tobytes()
        except Exception:
            return chunk  # Passthrough on any error

    async def shutdown(self) -> None:
        if self._aec_session:
            try:
                self._aec_session.close()
            except Exception:
                pass
        if self._bnr_session:
            try:
                self._bnr_session.close()
            except Exception:
                pass
