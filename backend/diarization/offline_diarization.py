"""Offline speaker diarization via pyannote.audio (full-file).

Used as POST-mode fallback when VibeVoice is unavailable or as the
primary POST diarizer before LLM summarization.

File: backend/diarization/offline_diarization.py
"""

from __future__ import annotations

import asyncio
from typing import Optional

import structlog

logger = structlog.get_logger(__name__)


class OfflineDiarization:
    """Full-file speaker diarization using pyannote.audio pipeline.

    Processes a WAV file and returns speaker-labeled time segments.
    """

    def __init__(self, num_speakers: Optional[int] = None, auth_token: Optional[str] = None):
        self.num_speakers = num_speakers
        self.auth_token = auth_token
        self._pipeline = None

    async def initialize(self) -> None:
        """Load pyannote pipeline (downloads models on first run)."""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._load_pipeline)

    def _load_pipeline(self) -> None:
        try:
            from pyannote.audio import Pipeline
            self._pipeline = Pipeline.from_pretrained(
                "pyannote/speaker-diarization-3.1",
                use_auth_token=self.auth_token,
            )
            try:
                import torch
                self._pipeline = self._pipeline.to(torch.device("cuda"))
            except Exception:
                pass
            logger.info("pyannote offline diarization loaded")
        except ImportError:
            logger.warning("pyannote.audio not installed — offline diarization unavailable")

    async def diarize(self, wav_path: str) -> list[dict]:
        """Diarize a WAV file.

        Returns:
            List of { speaker, start, end } dicts sorted by start time.
        """
        if self._pipeline is None:
            logger.warning("Diarization pipeline not loaded — returning empty result")
            return []

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._run_diarize, wav_path)

    def _run_diarize(self, wav_path: str) -> list[dict]:
        try:
            kwargs = {}
            if self.num_speakers:
                kwargs["num_speakers"] = self.num_speakers

            annotation = self._pipeline(wav_path, **kwargs)
            segments = []
            for turn, _, speaker in annotation.itertracks(yield_label=True):
                segments.append({
                    "speaker": speaker,
                    "start": round(turn.start, 3),
                    "end": round(turn.end, 3),
                })
            return sorted(segments, key=lambda x: x["start"])
        except Exception as exc:
            logger.error("Offline diarization failed", error=str(exc), path=wav_path)
            return []
