"""Language detection and ASR engine routing.

Auto-detects language from the first audio chunk using Whisper-tiny (CPU, ~39MB)
then selects the optimal ASR engine per CLAUDE.md §4.3.

Routing table:
  vi    → parakeet-vi   (NVIDIA Parakeet, native Vietnamese, 2GB VRAM)
  en    → faster-whisper (Whisper large-v3, 3GB VRAM)
  mixed → parakeet-vi   (Parakeet supports VN↔EN code-switching)

POST mode always uses vibevoice (best unified ASR+diarization+timestamps).

File: backend/asr/language_router.py
"""

from __future__ import annotations

import asyncio
from typing import Optional

import numpy as np
import structlog

logger = structlog.get_logger(__name__)

# Routing from CLAUDE.md §4.3
ROUTING_TABLE: dict[str, str] = {
    "vi": "parakeet-vi",
    "en": "faster-whisper",
    "mixed": "parakeet-vi",
}

POST_ENGINE = "vibevoice"
FALLBACK_ENGINE = "phowhisper"

SAMPLE_RATE = 16_000
# Whisper-tiny uses 30s context — we detect from first 3s
DETECTION_SECONDS = 3.0
DETECTION_BYTES = int(SAMPLE_RATE * 2 * DETECTION_SECONDS)


class LanguageRouter:
    """Detects language from initial audio and selects optimal ASR engine.

    Usage:
        router = LanguageRouter()
        lang = await router.detect_language(first_audio_chunk)
        engine_name = router.select_live_engine(lang)
    """

    def __init__(self):
        self._whisper_tiny = None   # Loaded lazily

    async def detect_language(self, audio_chunk: bytes) -> str:
        """Detect language from audio using Whisper-tiny (CPU).

        Args:
            audio_chunk: raw PCM bytes (16-bit, 16kHz, mono)

        Returns:
            "vi", "en", or "mixed"
        """
        if len(audio_chunk) < SAMPLE_RATE * 2 * 0.5:
            logger.debug("Audio too short for language detection — defaulting to vi")
            return "vi"

        try:
            loop = asyncio.get_event_loop()
            lang = await loop.run_in_executor(None, self._detect_sync, audio_chunk)
            logger.info("Language detected", language=lang)
            return lang
        except Exception as exc:
            logger.warning("Language detection failed, defaulting to vi", error=str(exc))
            return "vi"

    def _detect_sync(self, audio_chunk: bytes) -> str:
        """Synchronous language detection (runs in thread executor)."""
        if self._whisper_tiny is None:
            self._whisper_tiny = self._load_tiny_model()

        # Use at most DETECTION_BYTES worth of audio
        audio_bytes = audio_chunk[:DETECTION_BYTES]
        audio_np = (
            np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0
        )

        # Pad to 30s if shorter (Whisper requirement)
        target_samples = SAMPLE_RATE * 30
        if len(audio_np) < target_samples:
            audio_np = np.pad(audio_np, (0, target_samples - len(audio_np)))

        _, probs = self._whisper_tiny.detect_language(audio_np)

        vi_prob = probs.get("vi", 0.0)
        en_prob = probs.get("en", 0.0)

        logger.debug("Language probs", vi=round(vi_prob, 3), en=round(en_prob, 3))

        # Mixed: both languages have significant probability
        if vi_prob > 0.15 and en_prob > 0.15:
            return "mixed"
        if vi_prob > en_prob and vi_prob > 0.3:
            return "vi"
        if en_prob > vi_prob and en_prob > 0.3:
            return "en"

        # Default to Vietnamese for this Vietnamese-first platform
        return "vi"

    def _load_tiny_model(self):
        """Load Whisper-tiny on CPU for language detection only."""
        try:
            from faster_whisper import WhisperModel
            logger.info("Loading Whisper-tiny for language detection (CPU)")
            model = WhisperModel("tiny", device="cpu", compute_type="int8")
            return _WhisperTinyAdapter(model)
        except ImportError:
            raise RuntimeError(
                "faster-whisper required for language detection. "
                "Install with: pip install faster-whisper"
            )

    def select_live_engine(self, language: str) -> str:
        """Map detected language to the optimal LIVE ASR engine name."""
        engine = ROUTING_TABLE.get(language, "parakeet-vi")
        logger.debug("Engine selected for LIVE", language=language, engine=engine)
        return engine

    def select_post_engine(self) -> str:
        """Always use VibeVoice for POST processing."""
        return POST_ENGINE

    def select_fallback_engine(self) -> str:
        """Fallback engine if primary unavailable."""
        return FALLBACK_ENGINE


class _WhisperTinyAdapter:
    """Thin wrapper around faster-whisper for language detection only."""

    def __init__(self, model):
        self._model = model

    def detect_language(self, audio_np: np.ndarray) -> tuple[str, dict[str, float]]:
        """Returns (detected_language, {lang: probability}) dict."""
        import faster_whisper

        # faster-whisper detect_language API
        features = self._model.feature_extractor(audio_np)
        encoder_output = self._model.encode(features)
        results = self._model.model.detect_language(encoder_output)

        # results is list of (prob, lang) pairs
        probs = {lang: float(prob) for prob, lang in results[0]}
        best_lang = max(probs, key=probs.get) if probs else "vi"
        return best_lang, probs
