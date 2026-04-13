"""ASR Engine abstract interface and TranscriptSegment data model.

ALL ASR engines in MeetScribe MUST implement ASREngine.
See CLAUDE.md §4.1 for the authoritative specification.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import AsyncIterator, Optional


@dataclass
class TranscriptSegment:
    """Single unit of transcribed speech."""

    text: str
    start_time: float  # seconds from recording start
    end_time: float  # seconds from recording start
    confidence: float = 0.9  # 0.0 - 1.0
    language: str = "vi"  # ISO 639-1
    is_final: bool = True  # False = interim/partial result
    speaker: Optional[str] = None  # SPEAKER_00, SPEAKER_01, etc.
    source: str = "live"  # "live" or "post"
    timestamp: float = field(default_factory=time.time)  # wall clock

    def to_dict(self) -> dict:
        return {
            "text": self.text,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "confidence": self.confidence,
            "language": self.language,
            "is_final": self.is_final,
            "speaker": self.speaker,
            "source": self.source,
            "timestamp": self.timestamp,
        }


class ASREngine(ABC):
    """Abstract base class for all ASR engines.

    Every ASR engine in MeetScribe (Parakeet, faster-whisper, VibeVoice,
    PhoWhisper, Qwen3-ASR, GASR, Cloud, WhisperLiveKit, whisper-asr-webservice)
    MUST implement this interface.
    """

    @abstractmethod
    async def initialize(self, config: dict) -> None:
        """Load model, allocate GPU memory."""

    @abstractmethod
    async def transcribe_stream(
        self, audio_chunks: AsyncIterator[bytes]
    ) -> AsyncIterator[TranscriptSegment]:
        """LIVE mode: yield segments as audio streams in."""

    @abstractmethod
    async def transcribe_file(
        self, file_path: str, hotwords: Optional[list[str]] = None
    ) -> list[TranscriptSegment]:
        """POST mode: process complete audio file."""

    @abstractmethod
    async def shutdown(self) -> None:
        """Release GPU memory, cleanup."""

    @property
    @abstractmethod
    def capabilities(self) -> dict:
        """Return engine capabilities dict.

        Required keys:
            streaming: bool
            languages: list[str]
            gpu_required: bool
            gpu_vram_mb: int
            has_diarization: bool
            has_timestamps: bool
            model_name: str

        Optional keys:
            has_punctuation: bool
            has_forced_alignment: bool
            has_web_ui: bool
        """

    def supports_streaming(self) -> bool:
        return self.capabilities.get("streaming", False)

    def supports_language(self, lang: str) -> bool:
        return lang in self.capabilities.get("languages", [])
