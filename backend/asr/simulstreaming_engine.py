"""SimulStreaming engine wrapper — AlignAtt streaming policy.

SimulStreaming (ufal/SimulStreaming) wraps Parakeet or faster-whisper
with an AlignAtt simultaneous ASR policy that achieves low latency
while maintaining high accuracy. It is NOT a standalone ASR engine —
it WRAPS an existing engine (see CLAUDE.md §4.2 note).

Git submodule: engines/simulstreaming/ (ufal/SimulStreaming)

File: backend/asr/simulstreaming_engine.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import AsyncIterator, Optional

import structlog

from backend.asr.base import ASREngine, TranscriptSegment

logger = structlog.get_logger(__name__)

# Add SimulStreaming submodule to path
_SIMUL_PATH = Path(__file__).parent.parent.parent / "engines" / "simulstreaming"


class SimulStreamingEngine(ASREngine):
    """AlignAtt simultaneous ASR wrapper around Parakeet or faster-whisper.

    Initialization config keys:
        wrapped_engine: str       (default: "parakeet-vi")
        wrapped_config: dict      (passed to the wrapped engine's initialize())
        latency_seconds: float    (default: 1.0)  — max output delay
        chunk_size_ms: int        (default: 100)  — input chunk size
    """

    def __init__(self):
        self._wrapped: Optional[ASREngine] = None
        self._config: dict = {}
        self._initialized = False
        self._use_simul = False     # True if SimulStreaming lib is available

    async def initialize(self, config: dict) -> None:
        self._config = config
        wrapped_engine_name = config.get("wrapped_engine", "parakeet-vi")
        wrapped_config = config.get("wrapped_config", {})

        # Add SimulStreaming to path
        if _SIMUL_PATH.exists() and str(_SIMUL_PATH) not in sys.path:
            sys.path.insert(0, str(_SIMUL_PATH))

        # Try to import SimulStreaming library
        try:
            import simulstreaming  # noqa: F401
            self._use_simul = True
            logger.info("SimulStreaming library found")
        except ImportError:
            logger.warning(
                "SimulStreaming library not found in engines/simulstreaming — "
                "falling back to direct windowed streaming"
            )
            self._use_simul = False

        # Load the wrapped engine
        from backend.asr.engine_factory import ASREngineFactory
        self._wrapped = ASREngineFactory.create(wrapped_engine_name)
        await self._wrapped.initialize(wrapped_config)

        self._initialized = True
        logger.info(
            "SimulStreaming engine ready",
            wrapped=wrapped_engine_name,
            use_simul=self._use_simul,
        )

    async def transcribe_stream(
        self, audio_chunks: AsyncIterator[bytes]
    ) -> AsyncIterator[TranscriptSegment]:
        """Stream transcription with AlignAtt simultaneous policy.

        If SimulStreaming library is available, uses its policy for optimal
        latency/accuracy tradeoff. Otherwise falls back to wrapped engine directly.
        """
        if not self._initialized:
            raise RuntimeError("Engine not initialized")

        if self._use_simul:
            async for seg in self._simul_stream(audio_chunks):
                yield seg
        else:
            async for seg in self._wrapped.transcribe_stream(audio_chunks):
                yield seg

    async def _simul_stream(
        self, audio_chunks: AsyncIterator[bytes]
    ) -> AsyncIterator[TranscriptSegment]:
        """SimulStreaming AlignAtt policy — emits segments at low latency."""
        latency = self._config.get("latency_seconds", 1.0)

        try:
            import simulstreaming
            policy = simulstreaming.AlignAttPolicy(
                latency=latency,
                chunk_size_ms=self._config.get("chunk_size_ms", 100),
            )

            # SimulStreaming expects a synchronous generator — bridge async→sync
            import queue
            pcm_queue: queue.Queue = queue.Queue()
            result_queue: asyncio.Queue[TranscriptSegment] = asyncio.Queue()
            loop = asyncio.get_event_loop()

            async def feed_chunks():
                async for chunk in audio_chunks:
                    pcm_queue.put(chunk)
                pcm_queue.put(None)  # Sentinel

            def run_policy():
                def chunk_gen():
                    while True:
                        c = pcm_queue.get()
                        if c is None:
                            return
                        yield c

                for seg in policy.transcribe(self._wrapped, chunk_gen()):
                    result_queue.put_nowait(TranscriptSegment(
                        text=seg.text,
                        start_time=seg.start,
                        end_time=seg.end,
                        confidence=getattr(seg, "confidence", 0.9),
                        language=getattr(seg, "language", "vi"),
                        is_final=getattr(seg, "is_final", True),
                        source="live",
                    ))
                result_queue.put_nowait(None)  # Sentinel

            feed_task = asyncio.create_task(feed_chunks())
            policy_task = loop.run_in_executor(None, run_policy)

            await feed_task

            while True:
                seg = await result_queue.get()
                if seg is None:
                    break
                yield seg

        except Exception as exc:
            logger.error("SimulStreaming policy error, falling back", error=str(exc))
            async for seg in self._wrapped.transcribe_stream(audio_chunks):
                yield seg

    async def transcribe_file(
        self, file_path: str, hotwords: Optional[list[str]] = None
    ) -> list[TranscriptSegment]:
        """POST mode: delegates to wrapped engine."""
        if not self._initialized:
            raise RuntimeError("Engine not initialized")
        return await self._wrapped.transcribe_file(file_path, hotwords)

    async def shutdown(self) -> None:
        if self._wrapped:
            await self._wrapped.shutdown()
        self._initialized = False
        logger.info("SimulStreaming engine shutdown")

    @property
    def capabilities(self) -> dict:
        base = self._wrapped.capabilities if self._wrapped else {}
        return {
            **base,
            "streaming": True,
            "model_name": f"simulstreaming+{base.get('model_name', 'unknown')}",
        }
