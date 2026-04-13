"""Qwen3-ASR engine — Alibaba's SOTA multilingual ASR.

Supports 52 languages/dialects including Vietnamese, with:
- Streaming + offline unified inference
- Forced alignment timestamps
- Language auto-detection
- vLLM acceleration
- 0.6B and 1.7B variants

Install: pip install qwen-asr
Models: Qwen/Qwen3-ASR-1.7B, Qwen/Qwen3-ASR-0.6B
"""

from __future__ import annotations

from typing import AsyncIterator, Optional

from backend.asr.base import ASREngine, TranscriptSegment


class Qwen3ASREngine(ASREngine):
    """Qwen3-ASR — SOTA multilingual ASR (52 languages incl. Vietnamese).

    Key advantages:
    - 1.7B achieves SOTA among open-source ASR, competitive with proprietary APIs
    - Native Vietnamese support with language auto-detection
    - Streaming inference via qwen-asr toolkit
    - Forced alignment timestamps via Qwen3-ForcedAligner-0.6B
    - vLLM backend for production throughput (2000x at concurrency 128)
    """

    def __init__(self):
        self.model = None
        self.model_size = "1.7B"

    async def initialize(self, config: dict) -> None:
        self.model_size = config.get("model_size", "1.7B")
        model_name = f"Qwen/Qwen3-ASR-{self.model_size}"
        use_vllm = config.get("use_vllm", False)

        import torch
        from qwen_asr import Qwen3ASRModel

        if use_vllm:
            # vLLM backend — fastest inference, production use
            self.model = Qwen3ASRModel.LLM(
                model_name,
                dtype=torch.bfloat16,
                gpu_memory_utilization=config.get("gpu_memory_utilization", 0.6),
            )
        else:
            # Transformers backend — simpler setup
            self.model = Qwen3ASRModel.from_pretrained(
                model_name,
                dtype=torch.bfloat16,
                device_map=config.get("device", "cuda:0"),
            )

    async def transcribe_stream(
        self, audio_chunks: AsyncIterator[bytes]
    ) -> AsyncIterator[TranscriptSegment]:
        """Qwen3-ASR supports streaming via qwen-asr toolkit."""
        # Accumulate chunks into processable segments
        import numpy as np

        buffer = bytearray()
        chunk_duration = 5  # seconds
        chunk_bytes = chunk_duration * 16000 * 2  # 16kHz 16-bit

        async for chunk in audio_chunks:
            buffer.extend(chunk)
            if len(buffer) >= chunk_bytes:
                audio_np = np.frombuffer(buffer[:chunk_bytes], dtype=np.int16).astype(
                    np.float32
                ) / 32768.0

                results = self.model.transcribe(
                    audio=[audio_np],
                    language=None,  # auto-detect
                    return_time_stamps=True,
                )

                for r in results:
                    for ts in r.time_stamps:
                        yield TranscriptSegment(
                            text=ts.get("text", r.text),
                            start_time=ts.get("start", 0.0),
                            end_time=ts.get("end", 0.0),
                            confidence=0.95,
                            language=r.language or "auto",
                            is_final=True,
                            source="live",
                        )

                buffer = buffer[chunk_bytes:]

    async def transcribe_file(
        self, file_path: str, hotwords: Optional[list[str]] = None
    ) -> list[TranscriptSegment]:
        results = self.model.transcribe(
            audio=[file_path],
            language=None,  # auto-detect
            return_time_stamps=True,
        )

        segments = []
        for r in results:
            if r.time_stamps:
                for ts in r.time_stamps:
                    segments.append(
                        TranscriptSegment(
                            text=ts.get("text", ""),
                            start_time=ts.get("start", 0.0),
                            end_time=ts.get("end", 0.0),
                            confidence=0.95,
                            language=r.language or "auto",
                            is_final=True,
                            source="post",
                        )
                    )
            else:
                segments.append(
                    TranscriptSegment(
                        text=r.text,
                        start_time=0.0,
                        end_time=0.0,
                        confidence=0.95,
                        language=r.language or "auto",
                        is_final=True,
                        source="post",
                    )
                )
        return segments

    async def shutdown(self) -> None:
        del self.model
        self.model = None
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    @property
    def capabilities(self) -> dict:
        return {
            "streaming": True,
            "languages": [
                "vi", "en", "zh", "fr", "de", "es", "pt", "id", "it",
                "ko", "ru", "th", "ja", "tr", "hi", "ms", "nl", "sv",
                "da", "fi", "pl", "ar", "uk", "ro", "el", "hu", "cs",
                "no", "he", "ca",  # 30 languages + 22 Chinese dialects
            ],
            "gpu_required": True,
            "gpu_vram_mb": 4000 if self.model_size == "1.7B" else 2000,
            "has_diarization": False,
            "has_timestamps": True,
            "has_punctuation": True,
            "has_forced_alignment": True,
            "model_name": f"Qwen3-ASR-{self.model_size}",
        }
