"""faster-whisper ASR engine — English LIVE transcription.

Uses CTranslate2-optimised Whisper large-v3 for real-time English transcription.
This is the primary engine for English in LIVE mode (routed by LanguageRouter).

Capabilities:
  - Languages: en (primary), any whisper-supported language
  - Streaming: via VAD-chunked audio fed to transcribe()
  - Timestamps: word-level available
  - GPU: VRAM ~3GB (large-v3), ~1.5GB (medium)

File: backend/asr/faster_whisper_engine.py
"""

from __future__ import annotations

import asyncio
import time
from typing import AsyncIterator, Optional

import numpy as np
import structlog

from backend.asr.base import ASREngine, TranscriptSegment

logger = structlog.get_logger(__name__)

DEFAULT_MODEL = "large-v3"
DEFAULT_DEVICE = "cuda"
DEFAULT_COMPUTE_TYPE = "float16"
SAMPLE_RATE = 16_000


class FasterWhisperEngine(ASREngine):
    """English ASR via faster-whisper (CTranslate2 backend).

    Initialization config keys:
        model_size: str  (default: "large-v3")
        device: str      (default: "cuda")
        compute_type: str (default: "float16")
        language: str    (default: None = auto-detect)
        beam_size: int   (default: 5)
        vad_filter: bool (default: True)
    """

    def __init__(self):
        self._model = None
        self._config: dict = {}
        self._initialized = False

    async def initialize(self, config: dict) -> None:
        self._config = config
        model_size = config.get("model_size", DEFAULT_MODEL)
        device = config.get("device", DEFAULT_DEVICE)
        compute_type = config.get("compute_type", DEFAULT_COMPUTE_TYPE)

        logger.info(
            "Loading faster-whisper",
            model=model_size,
            device=device,
            compute_type=compute_type,
        )

        loop = asyncio.get_event_loop()
        self._model = await loop.run_in_executor(
            None,
            self._load_model,
            model_size,
            device,
            compute_type,
        )
        self._initialized = True
        logger.info("faster-whisper ready", model=model_size)

    def _load_model(self, model_size: str, device: str, compute_type: str):
        from faster_whisper import WhisperModel
        return WhisperModel(
            model_size,
            device=device,
            compute_type=compute_type,
        )

    async def transcribe_stream(
        self, audio_chunks: AsyncIterator[bytes]
    ) -> AsyncIterator[TranscriptSegment]:
        """LIVE streaming: buffer chunks into VAD windows, transcribe each.

        faster-whisper doesn't natively stream; we accumulate audio until
        VAD detects speech ends, then submit the window for transcription.
        This gives ~1-3s latency segments.
        """
        if not self._initialized:
            raise RuntimeError("Engine not initialized — call initialize() first")

        language = self._config.get("language", None)
        beam_size = self._config.get("beam_size", 5)
        vad_filter = self._config.get("vad_filter", True)

        # Accumulate audio in a rolling buffer
        buffer = bytearray()
        WINDOW_BYTES = SAMPLE_RATE * 2 * 3     # 3 seconds of audio
        recording_start = time.time()

        async for chunk in audio_chunks:
            buffer.extend(chunk)

            if len(buffer) < WINDOW_BYTES:
                continue

            # Transcribe current window
            window = bytes(buffer)
            buffer.clear()

            segments = await self._transcribe_pcm(
                window, language, beam_size, vad_filter,
                offset_seconds=(time.time() - recording_start - 3.0),
            )
            for seg in segments:
                yield seg

        # Flush remaining audio
        if buffer:
            segments = await self._transcribe_pcm(
                bytes(buffer), language, beam_size, vad_filter,
                offset_seconds=(time.time() - recording_start),
            )
            for seg in segments:
                yield seg

    async def transcribe_file(
        self, file_path: str, hotwords: Optional[list[str]] = None
    ) -> list[TranscriptSegment]:
        """POST mode: transcribe a complete audio/video file."""
        if not self._initialized:
            raise RuntimeError("Engine not initialized")

        language = self._config.get("language", None)
        beam_size = self._config.get("beam_size", 5)

        logger.info("Transcribing file", path=file_path, engine="faster-whisper")

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            self._run_transcribe_file,
            file_path,
            language,
            beam_size,
            hotwords,
        )
        return result

    def _run_transcribe_file(
        self,
        file_path: str,
        language: Optional[str],
        beam_size: int,
        hotwords: Optional[list[str]],
    ) -> list[TranscriptSegment]:
        segments_iter, info = self._model.transcribe(
            file_path,
            language=language,
            beam_size=beam_size,
            vad_filter=True,
            word_timestamps=True,
            initial_prompt=" ".join(hotwords) if hotwords else None,
        )

        results = []
        info_language = info.language if hasattr(info, 'language') else "en"

        for seg in segments_iter:
            # Normalize logprob (-1 to 1 range) to confidence (0-1)
            logprob = seg.avg_logprob if hasattr(seg, 'avg_logprob') else -1.0
            confidence = min(1.0, max(0.0, (logprob + 1.0) / 2.0))

            text = seg.text.strip()
            if not text:
                continue

            results.append(TranscriptSegment(
                text=text,
                start_time=seg.start if hasattr(seg, 'start') else 0.0,
                end_time=seg.end if hasattr(seg, 'end') else 0.0,
                confidence=confidence,
                language=info_language,
                is_final=True,
                source="post",
            ))

        return results

    async def _transcribe_pcm(
        self,
        pcm_bytes: bytes,
        language: Optional[str],
        beam_size: int,
        vad_filter: bool,
        offset_seconds: float,
    ) -> list[TranscriptSegment]:
        """Run transcription on raw PCM bytes via thread executor."""
        if len(pcm_bytes) < SAMPLE_RATE * 2 * 0.3:  # < 300ms — skip
            return []

        audio_np = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32) / 32768.0

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self._run_transcribe_np,
            audio_np,
            language,
            beam_size,
            vad_filter,
            offset_seconds,
        )

    def _run_transcribe_np(
        self,
        audio: np.ndarray,
        language: Optional[str],
        beam_size: int,
        vad_filter: bool,
        offset_seconds: float,
    ) -> list[TranscriptSegment]:
        segments_iter, info = self._model.transcribe(
            audio,
            language=language,
            beam_size=beam_size,
            vad_filter=vad_filter,
            word_timestamps=False,
        )

        results = []
        info_language = info.language if hasattr(info, 'language') else "en"

        for seg in segments_iter:
            text = seg.text.strip()
            if not text:
                continue

            logprob = seg.avg_logprob if hasattr(seg, 'avg_logprob') else -1.0
            confidence = min(1.0, max(0.0, (logprob + 1.0) / 2.0))

            results.append(TranscriptSegment(
                text=text,
                start_time=max(0.0, offset_seconds + seg.start) if hasattr(seg, 'start') else offset_seconds,
                end_time=max(0.0, offset_seconds + seg.end) if hasattr(seg, 'end') else offset_seconds,
                confidence=confidence,
                language=info_language,
                is_final=True,
                source="live",
            ))
        return results

    async def shutdown(self) -> None:
        self._model = None
        self._initialized = False
        logger.info("faster-whisper unloaded")

    @property
    def capabilities(self) -> dict:
        return {
            "streaming": True,
            "languages": ["en", "vi", "zh", "fr", "de", "ja", "ko"],
            "gpu_required": False,   # Can run on CPU (slower)
            "gpu_vram_mb": 3000,     # large-v3 on GPU
            "has_diarization": False,
            "has_timestamps": True,
            "has_punctuation": True,
            "model_name": f"whisper-{self._config.get('model_size', DEFAULT_MODEL)}",
        }