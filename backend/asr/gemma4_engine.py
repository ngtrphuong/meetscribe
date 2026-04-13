"""Gemma 4 Multimodal ASR Engine — audio-text-to-text via Google Gemma 4.

Uses google/gemma-4-E2B-it or google/gemma-4-E4B-it for high-quality
audio transcription + understanding. Best used for POST mode (file transcription)
since it requires ~11-20 GB VRAM and inference is slower than dedicated ASR models.

Capabilities vs other engines:
- Higher transcription quality through LLM reasoning
- Can understand audio context (accents, emotion, overlapping speech)
- Supports Vietnamese and English natively
- Suitable for POST processing where quality > speed

File: backend/asr/gemma4_engine.py
"""

from __future__ import annotations

import asyncio
import tempfile
import os
from typing import AsyncIterator, Optional

import structlog

from backend.asr.base import ASREngine, TranscriptSegment

logger = structlog.get_logger(__name__)

DEFAULT_MODEL = "google/gemma-4-E2B-it"  # ~11-13 GB VRAM
SAMPLE_RATE = 16_000

TRANSCRIPTION_PROMPT = (
    "Please transcribe the following audio exactly as spoken. "
    "Include all words, preserve the original language (Vietnamese or English), "
    "and do not add commentary. Output only the transcription text."
)


class Gemma4Engine(ASREngine):
    """Google Gemma 4 multimodal ASR engine.

    Uses Gemma 4's audio-text-to-text capability for transcription.
    Best for POST mode (high quality, full-file transcription).

    Initialization config keys:
        model_name: str   (default: "google/gemma-4-E2B-it")
        device: str       (default: "auto" — let transformers choose)
        max_new_tokens: int (default: 2048)
    """

    def __init__(self):
        self._model = None
        self._processor = None
        self._config: dict = {}
        self._initialized = False

    async def initialize(self, config: dict) -> None:
        self._config = config
        model_name = config.get("model_name", DEFAULT_MODEL)
        logger.info("Loading Gemma 4 multimodal model", model=model_name)

        loop = asyncio.get_event_loop()
        self._model, self._processor = await loop.run_in_executor(
            None, self._load_model, model_name
        )
        self._initialized = True
        logger.info("Gemma 4 ready", model=model_name)

    def _load_model(self, model_name: str):
        import torch
        from transformers import AutoProcessor, AutoModelForImageTextToText

        processor = AutoProcessor.from_pretrained(
            model_name,
            padding_side="left",
        )
        model = AutoModelForImageTextToText.from_pretrained(
            model_name,
            torch_dtype=torch.bfloat16,
            device_map="auto",
            attn_implementation="sdpa",
        )
        model.eval()
        return model, processor

    def _build_messages(self, audio_path: str) -> list[dict]:
        return [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": TRANSCRIPTION_PROMPT},
                    {"type": "audio", "url": f"file://{os.path.abspath(audio_path)}"},
                ],
            }
        ]

    def _run_transcription(self, audio_path: str) -> str:
        import torch

        messages = self._build_messages(audio_path)
        inputs = self._processor.apply_chat_template(
            messages,
            tokenize=True,
            add_generation_prompt=True,
            return_dict=True,
            return_tensors="pt",
        ).to(self._model.device, dtype=torch.bfloat16)

        input_len = inputs["input_ids"].shape[-1]
        max_new_tokens = self._config.get("max_new_tokens", 2048)

        with torch.inference_mode():
            outputs = self._model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                do_sample=False,
            )

        decoded = self._processor.decode(
            outputs[0][input_len:], skip_special_tokens=True
        )
        return decoded.strip()

    async def transcribe_file(
        self, file_path: str, hotwords: Optional[list[str]] = None
    ) -> list[TranscriptSegment]:
        if not self._initialized:
            raise RuntimeError("Gemma4Engine not initialized. Call initialize() first.")

        loop = asyncio.get_event_loop()
        text = await loop.run_in_executor(None, self._run_transcription, file_path)

        if not text:
            return []

        # Estimate duration from file
        duration = self._estimate_duration(file_path)

        return [TranscriptSegment(
            text=text,
            start_time=0.0,
            end_time=duration,
            confidence=0.92,
            language="vi",   # auto-detected by Gemma, report vi as default
            is_final=True,
            source="post",
        )]

    def _estimate_duration(self, file_path: str) -> float:
        """Estimate audio duration from WAV header or file size."""
        try:
            import wave
            with wave.open(file_path, "rb") as wf:
                return wf.getnframes() / wf.getframerate()
        except Exception:
            # Fallback: 1 byte = ~1/32000s for 16-bit 16kHz mono
            try:
                return os.path.getsize(file_path) / (SAMPLE_RATE * 2)
            except Exception:
                return 0.0

    async def transcribe_stream(
        self, audio_chunks: AsyncIterator[bytes]
    ) -> AsyncIterator[TranscriptSegment]:
        """Gemma 4 is not designed for real-time streaming — buffer and batch."""
        buffer = bytearray()
        async for chunk in audio_chunks:
            buffer.extend(chunk)

        if not buffer:
            return

        # Write to temp WAV and transcribe
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            tmp_path = f.name
            self._write_wav(f, bytes(buffer))

        try:
            segments = await self.transcribe_file(tmp_path)
            for seg in segments:
                yield seg
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    def _write_wav(self, f, pcm: bytes) -> None:
        import struct
        sample_rate = SAMPLE_RATE
        n_channels = 1
        bits_per_sample = 16
        data_size = len(pcm)
        f.write(b"RIFF")
        f.write(struct.pack("<I", 36 + data_size))
        f.write(b"WAVE")
        f.write(b"fmt ")
        f.write(struct.pack("<IHHIIHH", 16, 1, n_channels, sample_rate,
                            sample_rate * n_channels * bits_per_sample // 8,
                            n_channels * bits_per_sample // 8, bits_per_sample))
        f.write(b"data")
        f.write(struct.pack("<I", data_size))
        f.write(pcm)

    async def shutdown(self) -> None:
        if self._model is not None:
            try:
                import torch
                del self._model
                del self._processor
                torch.cuda.empty_cache()
            except Exception:
                pass
        self._model = None
        self._processor = None
        self._initialized = False
        logger.info("Gemma 4 unloaded")

    @property
    def capabilities(self) -> dict:
        model_name = self._config.get("model_name", DEFAULT_MODEL)
        # E4B uses more VRAM
        vram = 18000 if "E4B" in model_name else 13000
        return {
            "streaming": False,       # buffer-then-batch only
            "languages": ["vi", "en", "mixed"],
            "gpu_required": True,
            "gpu_vram_mb": vram,
            "has_diarization": False,
            "has_timestamps": False,  # outputs full text only
            "has_punctuation": True,
            "model_name": model_name,
        }
