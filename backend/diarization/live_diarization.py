"""Real-time speaker diarization via diart (500ms update intervals).

diart wraps pyannote.audio models to produce streaming speaker segments.
GPU VRAM: ~2GB (segmentation + embedding models).

Output: speaker labels (SPEAKER_00, SPEAKER_01, …) with time boundaries,
pushed to an asyncio.Queue for the orchestrator to merge with ASR segments.

File: backend/diarization/live_diarization.py
"""

from __future__ import annotations

import asyncio
import time
from typing import Optional

import numpy as np
import structlog

logger = structlog.get_logger(__name__)

SAMPLE_RATE = 16_000
UPDATE_INTERVAL_MS = 500          # diart update cadence
CHUNK_DURATION = UPDATE_INTERVAL_MS / 1000.0


class LiveDiarization:
    """Real-time speaker diarization using diart streaming pipeline.

    Usage:
        diar = LiveDiarization()
        await diar.start(audio_queue)
        # diar.speaker_queue receives { speaker, start, end } dicts
        await diar.stop()
    """

    def __init__(self, num_speakers: Optional[int] = None):
        self.num_speakers = num_speakers
        self.speaker_queue: asyncio.Queue[dict] = asyncio.Queue(maxsize=500)
        self._pipeline = None
        self._task: Optional[asyncio.Task] = None
        self._running = False

    async def start(self, audio_queue: asyncio.Queue[bytes]) -> None:
        """Start the diarization pipeline consuming audio from audio_queue."""
        self._running = True
        self._task = asyncio.create_task(
            self._run_pipeline(audio_queue),
            name="live-diarization",
        )
        logger.info("Live diarization started")

    async def stop(self) -> None:
        """Stop the diarization pipeline."""
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Live diarization stopped")

    async def _run_pipeline(self, audio_queue: asyncio.Queue[bytes]) -> None:
        """Main diarization loop: reads audio chunks and runs diart."""
        try:
            import diart
            import diart.operators as dops
            import diart.sources as src
            from diart import SpeakerDiarization, SpeakerDiarizationConfig
            from pyannote.audio import Pipeline
            import rx
            from rx.scheduler import NewThreadScheduler

            config = SpeakerDiarizationConfig(
                duration=UPDATE_INTERVAL_MS / 1000.0,
                step=UPDATE_INTERVAL_MS / 1000.0,
                latency=UPDATE_INTERVAL_MS / 1000.0,
                tau_active=0.507,
                rho_update=0.006,
                delta_new=1.057,
            )
            pipeline = SpeakerDiarization(config=config)

        except ImportError:
            logger.warning(
                "diart not installed — using stub diarization (SPEAKER_00 only). "
                "Install: pip install diart"
            )
            await self._run_stub_pipeline(audio_queue)
            return

        except Exception as exc:
            logger.error("Failed to initialise diart pipeline", error=str(exc))
            await self._run_stub_pipeline(audio_queue)
            return

        # Buffer audio and process in UPDATE_INTERVAL windows
        buffer = bytearray()
        target_bytes = int(SAMPLE_RATE * 2 * CHUNK_DURATION)
        wall_start = time.time()

        try:
            while self._running:
                try:
                    chunk = await asyncio.wait_for(audio_queue.get(), timeout=1.0)
                    buffer.extend(chunk)
                except asyncio.TimeoutError:
                    continue

                if len(buffer) < target_bytes:
                    continue

                window = bytes(buffer[:target_bytes])
                buffer = buffer[target_bytes:]

                # Process synchronously in executor
                loop = asyncio.get_event_loop()
                annotation = await loop.run_in_executor(
                    None, self._process_window, pipeline, window, time.time() - wall_start
                )

                if annotation:
                    for turn, _, speaker in annotation.itertracks(yield_label=True):
                        event = {
                            "speaker": speaker,
                            "start": turn.start,
                            "end": turn.end,
                        }
                        try:
                            self.speaker_queue.put_nowait(event)
                        except asyncio.QueueFull:
                            pass

        except asyncio.CancelledError:
            pass

    def _process_window(self, pipeline, pcm_bytes: bytes, offset: float):
        """Run diart on a PCM window — called in thread executor."""
        try:
            audio_np = (
                np.frombuffer(pcm_bytes, dtype=np.int16)
                .astype(np.float32) / 32768.0
            )
            # diart expects (channels, samples) tensor
            import torch
            audio_tensor = torch.from_numpy(audio_np).unsqueeze(0)
            from pyannote.core import SlidingWindowFeature, SlidingWindow

            sw = SlidingWindow(start=offset, duration=CHUNK_DURATION, step=CHUNK_DURATION)
            features = SlidingWindowFeature(audio_np.reshape(1, -1).T, sw)
            # diart pipeline call signature varies by version
            result = pipeline(features)
            return result
        except Exception as exc:
            logger.debug("Diarization window error", error=str(exc))
            return None

    async def _run_stub_pipeline(self, audio_queue: asyncio.Queue[bytes]) -> None:
        """Stub diarization: labels all audio as SPEAKER_00.

        Used when diart is not installed (dev/CI environments).
        """
        wall_start = time.time()
        try:
            while self._running:
                try:
                    await asyncio.wait_for(audio_queue.get(), timeout=1.0)
                    now = time.time() - wall_start
                    event = {
                        "speaker": "SPEAKER_00",
                        "start": max(0.0, now - CHUNK_DURATION),
                        "end": now,
                    }
                    try:
                        self.speaker_queue.put_nowait(event)
                    except asyncio.QueueFull:
                        pass
                except asyncio.TimeoutError:
                    continue
        except asyncio.CancelledError:
            pass
