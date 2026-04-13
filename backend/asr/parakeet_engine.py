"""NVIDIA Parakeet Vietnamese ASR engine — PRIMARY LIVE engine.

Uses NVIDIA NeMo Parakeet-CTC-0.6B-Vi for real-time Vietnamese transcription.
~2GB GPU VRAM, native punctuation & capitalisation, code-switching VN↔EN.

Capabilities:
  - Primary language: Vietnamese (vi)
  - Code-switching: VN↔EN
  - Streaming: SimulStreaming wrapper (AlignAtt policy)
  - Timestamps: frame-level CTC alignment
  - GPU VRAM: ~2 GB

File: backend/asr/parakeet_engine.py
"""

from __future__ import annotations

import asyncio
import io
import time
import wave
from typing import AsyncIterator, Optional

import numpy as np
import structlog

from backend.asr.base import ASREngine, TranscriptSegment

logger = structlog.get_logger(__name__)

MODEL_NAME = "nvidia/parakeet-ctc-0.6b-vi"
SAMPLE_RATE = 16_000
WINDOW_SECONDS = 5      # Transcription window for streaming approximation
STRIDE_SECONDS = 3      # Slide window every N seconds


class ParakeetVietnameseEngine(ASREngine):
    """Vietnamese ASR via NVIDIA NeMo Parakeet-CTC-0.6B-Vi.

    Initialization config keys:
        model_name: str  (default: "nvidia/parakeet-ctc-0.6b-vi")
        device: str      (default: "cuda")
        map_location: str (default: "cuda")
    """

    def __init__(self):
        self._model = None
        self._config: dict = {}
        self._initialized = False

    async def initialize(self, config: dict) -> None:
        self._config = config
        model_name = config.get("model_name", MODEL_NAME)

        logger.info("Loading Parakeet Vietnamese ASR", model=model_name)

        loop = asyncio.get_event_loop()
        self._model = await loop.run_in_executor(None, self._load_model, model_name)
        self._initialized = True
        logger.info("Parakeet Vietnamese ASR ready", model=model_name)

    def _load_model(self, model_name: str):
        import nemo.collections.asr as nemo_asr
        model = nemo_asr.models.EncDecCTCModelBPE.from_pretrained(model_name)
        model.eval()
        try:
            import torch
            model = model.cuda()
        except Exception:
            pass
        return model

    async def transcribe_stream(
        self, audio_chunks: AsyncIterator[bytes]
    ) -> AsyncIterator[TranscriptSegment]:
        """LIVE streaming with sliding window buffering.

        Accumulates audio into windows and transcribes each window.
        For true frame-aligned streaming, use SimulStreamingEngine wrapper.
        """
        if not self._initialized:
            raise RuntimeError("Engine not initialized")

        buffer = bytearray()
        window_bytes = SAMPLE_RATE * 2 * WINDOW_SECONDS
        stride_bytes = SAMPLE_RATE * 2 * STRIDE_SECONDS
        recording_start = time.time()
        window_index = 0

        async for chunk in audio_chunks:
            buffer.extend(chunk)

            if len(buffer) < window_bytes:
                continue

            window_pcm = bytes(buffer[:window_bytes])
            buffer = buffer[stride_bytes:]      # Slide forward

            offset = window_index * STRIDE_SECONDS
            window_index += 1

            segments = await self._transcribe_pcm(window_pcm, offset)
            for seg in segments:
                yield seg

        # Flush remaining
        if len(buffer) > SAMPLE_RATE * 2 * 0.3:  # > 300ms
            offset = window_index * STRIDE_SECONDS
            segments = await self._transcribe_pcm(bytes(buffer), offset)
            for seg in segments:
                yield seg

    async def transcribe_file(
        self, file_path: str, hotwords: Optional[list[str]] = None
    ) -> list[TranscriptSegment]:
        """POST mode: transcribe a complete audio file."""
        if not self._initialized:
            raise RuntimeError("Engine not initialized")

        logger.info("Transcribing file", path=file_path, engine="parakeet-vi")

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._run_transcribe_file, file_path)

    def _run_transcribe_file(self, file_path: str) -> list[TranscriptSegment]:
        output = self._model.transcribe([file_path], return_hypotheses=True)

        segments = []
        if output and output[0]:
            hyp = output[0][0] if isinstance(output[0], list) else output[0]
            text = hyp.text if hasattr(hyp, "text") else str(hyp)

            # Parakeet CTC doesn't give per-segment timestamps in basic mode
            # Use the whole file as one segment; SimulStreaming gives finer alignment
            segments.append(TranscriptSegment(
                text=text.strip(),
                start_time=0.0,
                end_time=0.0,
                confidence=0.9,
                language="vi",
                is_final=True,
                source="post",
            ))
        return segments

    async def _transcribe_pcm(
        self, pcm_bytes: bytes, offset_seconds: float
    ) -> list[TranscriptSegment]:
        """Transcribe a PCM buffer, returning a list of segments."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self._run_transcribe_pcm, pcm_bytes, offset_seconds
        )

    def _run_transcribe_pcm(
        self, pcm_bytes: bytes, offset_seconds: float
    ) -> list[TranscriptSegment]:
        # Write PCM to an in-memory WAV so NeMo can read it
        wav_buf = io.BytesIO()
        with wave.open(wav_buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(pcm_bytes)
        wav_buf.seek(0)

        # NeMo needs a file path — write to a temp file
        import tempfile
        import os
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp.write(wav_buf.read())
            tmp_path = tmp.name

        try:
            output = self._model.transcribe([tmp_path], return_hypotheses=True)
        finally:
            os.unlink(tmp_path)

        segments = []
        if output and output[0]:
            hyp = output[0][0] if isinstance(output[0], list) else output[0]
            text = (hyp.text if hasattr(hyp, "text") else str(hyp)).strip()
            if text:
                duration = len(pcm_bytes) / (SAMPLE_RATE * 2)
                segments.append(TranscriptSegment(
                    text=text,
                    start_time=offset_seconds,
                    end_time=offset_seconds + duration,
                    confidence=0.9,
                    language="vi",
                    is_final=True,
                    source="live",
                ))
        return segments

    async def shutdown(self) -> None:
        if self._model is not None:
            try:
                import torch
                del self._model
                torch.cuda.empty_cache()
            except Exception:
                pass
        self._model = None
        self._initialized = False
        logger.info("Parakeet Vietnamese ASR unloaded")

    @property
    def capabilities(self) -> dict:
        return {
            "streaming": True,
            "languages": ["vi", "en"],      # Code-switching supported
            "gpu_required": True,
            "gpu_vram_mb": 2000,
            "has_diarization": False,
            "has_timestamps": True,
            "has_punctuation": True,
            "model_name": self._config.get("model_name", MODEL_NAME),
        }
