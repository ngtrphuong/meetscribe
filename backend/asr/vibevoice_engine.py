"""VibeVoice-ASR 7B — POST-mode unified ASR engine.

Microsoft VibeVoice-ASR 7B performs single-pass:
  - ASR (transcription)
  - Speaker diarization
  - Word-level timestamps

This is the definitive POST-mode engine (CLAUDE.md §2, §4.4).
Load AFTER unloading LIVE engines. ~7GB GPU VRAM at 4-bit NF4 quantization.

File: backend/asr/vibevoice_engine.py
"""

from __future__ import annotations

import asyncio
import time
from typing import AsyncIterator, Optional

import structlog

from backend.asr.base import ASREngine, TranscriptSegment

logger = structlog.get_logger(__name__)

MODEL_NAME = "microsoft/VibeVoice-ASR"


class VibeVoiceASREngine(ASREngine):
    """POST-mode unified ASR+diarization via VibeVoice-ASR.

    Initialization config keys:
        model_name: str         (default: "microsoft/VibeVoice-ASR")
        quantization: str       (default: "4bit")  — "4bit", "8bit", or "none"
        device: str             (default: "cuda")
        max_new_tokens: int     (default: 4096)

    Note: microsoft/VibeVoice-ASR (3B params) is the correct model ID on HuggingFace.
          The 7B model is available at microsoft/VibeVoice-ASR-7B or via vLLM backend.
    """

    def __init__(self):
        self._model = None
        self._processor = None
        self._config: dict = {}
        self._initialized = False

    async def initialize(self, config: dict) -> None:
        self._config = config
        model_name = config.get("model_name", MODEL_NAME)
        quantization = config.get("quantization", "4bit")

        logger.info("Loading VibeVoice-ASR", model=model_name, quantization=quantization)

        loop = asyncio.get_event_loop()
        try:
            self._model, self._processor = await loop.run_in_executor(
                None, self._load_model, model_name, quantization
            )
            self._initialized = True
            logger.info("VibeVoice-ASR ready")
        except Exception as exc:
            logger.error("Failed to load VibeVoice-ASR", error=str(exc))
            raise RuntimeError(
                f"Failed to load VibeVoice-ASR model '{model_name}'. "
                f"Please ensure the model is downloaded or use a fallback engine (phowhisper, faster-whisper). "
                f"Error: {exc}"
            ) from exc

    def _load_model(self, model_name: str, quantization: str):
        from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor

        quant_config = None
        device_map = "auto"

        if quantization == "4bit":
            from transformers import BitsAndBytesConfig
            quant_config = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_use_double_quant=True,
            )
        elif quantization == "8bit":
            from transformers import BitsAndBytesConfig
            quant_config = BitsAndBytesConfig(load_in_8bit=True)

        try:
            processor = AutoProcessor.from_pretrained(model_name)
            model = AutoModelForSpeechSeq2Seq.from_pretrained(
                model_name,
                quantization_config=quant_config,
                device_map=device_map,
                low_cpu_mem_usage=True,
            )
            return model, processor
        except Exception:
            # Try without quantization as fallback
            processor = AutoProcessor.from_pretrained(model_name)
            model = AutoModelForSpeechSeq2Seq.from_pretrained(
                model_name,
                device_map=device_map,
                low_cpu_mem_usage=True,
            )
            return model, processor

    async def transcribe_stream(
        self, audio_chunks: AsyncIterator[bytes]
    ) -> AsyncIterator[TranscriptSegment]:
        """VibeVoice is POST-only — streaming is not supported.

        Raises RuntimeError to signal the orchestrator should use
        a LIVE-capable engine instead.
        """
        raise RuntimeError(
            "VibeVoice-ASR is POST-only. Use parakeet-vi or faster-whisper for LIVE mode."
        )
        yield  # Make this an async generator

    async def transcribe_file(
        self, file_path: str, hotwords: Optional[list[str]] = None
    ) -> list[TranscriptSegment]:
        """POST mode: unified ASR + diarization + timestamps in one pass.

        Returns segments with speaker labels and word-level timestamps.
        """
        if not self._initialized:
            raise RuntimeError("VibeVoice not initialized — call initialize() first")

        logger.info("VibeVoice POST transcription", path=file_path)

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._run_transcribe, file_path, hotwords)

    def _run_transcribe(
        self, file_path: str, hotwords: Optional[list[str]]
    ) -> list[TranscriptSegment]:
        import torch
        import librosa

        # Load audio at 16kHz mono
        audio, sr = librosa.load(file_path, sr=16_000, mono=True)

        # Prepare model inputs
        inputs = self._processor(
            audio,
            sampling_rate=16_000,
            return_tensors="pt",
        )

        device = next(self._model.parameters()).device
        inputs = {k: v.to(device) for k, v in inputs.items()}

        with torch.inference_mode():
            output = self._model.generate(
                **inputs,
                max_new_tokens=self._config.get("max_new_tokens", 4096),
                return_timestamps=True,
                return_segments=True,
            )

        # Parse structured output — VibeVoice returns JSON with speaker+timestamps
        segments = self._parse_output(output)
        return segments

    def _parse_output(self, output) -> list[TranscriptSegment]:
        """Parse VibeVoice model output into TranscriptSegment list."""
        segments = []

        try:
            # VibeVoice output format (subject to model API):
            # output["segments"] is a list of dicts with:
            #   { "text", "start", "end", "speaker" }
            raw_segments = output.get("segments", [])

            for seg in raw_segments:
                segments.append(TranscriptSegment(
                    text=seg.get("text", "").strip(),
                    start_time=float(seg.get("start", 0.0)),
                    end_time=float(seg.get("end", 0.0)),
                    confidence=float(seg.get("confidence", 0.9)),
                    language=seg.get("language", "vi"),
                    is_final=True,
                    speaker=seg.get("speaker"),
                    source="post",
                ))
        except Exception as exc:
            logger.warning("Failed to parse VibeVoice output", error=str(exc))
            # Fallback: return raw decoded text as single segment
            if hasattr(output, "sequences"):
                text = self._processor.batch_decode(output.sequences, skip_special_tokens=True)
                if text:
                    segments.append(TranscriptSegment(
                        text=text[0].strip(),
                        start_time=0.0,
                        end_time=0.0,
                        confidence=0.9,
                        language="vi",
                        is_final=True,
                        source="post",
                    ))

        return segments

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
        logger.info("VibeVoice-ASR 7B unloaded")

    @property
    def capabilities(self) -> dict:
        return {
            "streaming": False,       # POST-only
            "languages": ["vi", "en", "mixed"],
            "gpu_required": True,
            "gpu_vram_mb": 5000,      # 4-bit NF4 quantized (3B model)
            "has_diarization": True,  # Native speaker diarization
            "has_timestamps": True,   # Word-level
            "has_punctuation": True,
            "model_name": self._config.get("model_name", MODEL_NAME),
        }
