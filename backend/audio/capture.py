"""Audio capture for MeetScribe — system loopback + microphone.

Captures 16-bit PCM mono at 16kHz from:
  - System audio (loopback): captures Zoom/Teams/Meet output
  - Microphone: captures user's own voice in parallel

Audio chunks are pushed into an asyncio.Queue for downstream processing
(ASR engine, Maxine preprocessor, WebSocket level meter).

DECREE 356: Raw audio held in memory only. WAV saved to disk only if
consent_recording=True. Audio is destroyed after transcript is committed.
"""

from __future__ import annotations

import asyncio
import sys
from collections import deque
from typing import AsyncIterator, Optional

import numpy as np
import structlog

logger = structlog.get_logger(__name__)

# Target audio parameters for all ASR engines
SAMPLE_RATE = 16_000    # Hz
CHANNELS = 1            # Mono
DTYPE = "int16"         # 16-bit PCM
CHUNK_DURATION = 0.1    # seconds per chunk → 1600 samples = 3200 bytes
CHUNK_SAMPLES = int(SAMPLE_RATE * CHUNK_DURATION)
CHUNK_BYTES = CHUNK_SAMPLES * 2  # int16 = 2 bytes/sample


class AudioCapture:
    """Captures system audio (loopback) and/or microphone in parallel.

    Usage:
        capture = AudioCapture(system_device_id=1, mic_device_id=0)
        await capture.start()
        async for chunk in capture.stream():
            # chunk: bytes (16-bit PCM, 16kHz, mono)
            process(chunk)
        await capture.stop()
    """

    def __init__(
        self,
        system_device_id: Optional[int] = None,
        mic_device_id: Optional[int] = None,
        chunk_duration: float = CHUNK_DURATION,
    ):
        self.system_device_id = system_device_id
        self.mic_device_id = mic_device_id
        self.chunk_duration = chunk_duration

        self._queue: asyncio.Queue[bytes] = asyncio.Queue(maxsize=200)
        self._running = False
        self._streams: list = []

        # Level meters (0.0 – 1.0) for WebSocket UI
        self.system_level: float = 0.0
        self.mic_level: float = 0.0

    async def start(self) -> None:
        """Open audio streams and begin capturing."""
        if self._running:
            return

        try:
            import sounddevice as sd
        except ImportError:
            raise RuntimeError(
                "sounddevice is not installed. Run: pip install sounddevice"
            )

        self._running = True
        loop = asyncio.get_event_loop()

        if self.system_device_id is not None:
            self._start_stream(sd, loop, self.system_device_id, source="system")

        if self.mic_device_id is not None:
            self._start_stream(sd, loop, self.mic_device_id, source="mic")

        if not self._streams:
            # No specific devices — use default input
            self._start_stream(sd, loop, None, source="mic")

        logger.info(
            "Audio capture started",
            system_device=self.system_device_id,
            mic_device=self.mic_device_id,
        )

    def _start_stream(self, sd, loop, device_id, source: str) -> None:
        """Open a sounddevice InputStream in callback mode."""

        def callback(indata: np.ndarray, frames: int, time_info, status):
            if status:
                logger.debug("Audio stream status", status=str(status), source=source)

            # Convert to 16kHz mono int16
            audio = _to_mono_int16(indata)

            # Update level meter
            rms = float(np.sqrt(np.mean(audio.astype(np.float32) ** 2))) / 32768.0
            if source == "system":
                self.system_level = min(rms * 4, 1.0)
            else:
                self.mic_level = min(rms * 4, 1.0)

            # Push to async queue (non-blocking from callback thread)
            try:
                loop.call_soon_threadsafe(
                    self._queue.put_nowait, audio.tobytes()
                )
            except asyncio.QueueFull:
                pass  # Drop chunk if consumer is too slow

        chunk_samples = int(SAMPLE_RATE * self.chunk_duration)

        try:
            stream = sd.InputStream(
                samplerate=SAMPLE_RATE,
                channels=CHANNELS,
                dtype=DTYPE,
                blocksize=chunk_samples,
                device=device_id,
                callback=callback,
            )
            stream.start()
            self._streams.append(stream)
            logger.debug("Opened audio stream", device=device_id, source=source)
        except Exception as exc:
            logger.error("Failed to open audio stream", device=device_id, error=str(exc))

    async def stop(self) -> None:
        """Stop all audio streams."""
        self._running = False
        for stream in self._streams:
            try:
                stream.stop()
                stream.close()
            except Exception:
                pass
        self._streams.clear()
        logger.info("Audio capture stopped")

    async def stream(self) -> AsyncIterator[bytes]:
        """Async generator yielding PCM chunks while capture is running.

        Yields:
            bytes: 16-bit PCM, mono, 16kHz, CHUNK_DURATION seconds long
        """
        while self._running or not self._queue.empty():
            try:
                chunk = await asyncio.wait_for(self._queue.get(), timeout=0.5)
                yield chunk
            except asyncio.TimeoutError:
                if not self._running:
                    break

    def get_levels(self) -> dict:
        """Return current audio level meters for WebSocket broadcast."""
        return {
            "system": round(self.system_level, 3),
            "mic": round(self.mic_level, 3),
        }

    @property
    def is_running(self) -> bool:
        return self._running


def _to_mono_int16(indata: np.ndarray) -> np.ndarray:
    """Convert sounddevice callback data to mono int16 at source sample rate.

    Resampling to 16kHz is handled by sounddevice's samplerate parameter.
    This function only handles channel mixing if multi-channel input arrives.
    """
    if indata.ndim > 1 and indata.shape[1] > 1:
        # Mix down to mono by averaging channels
        audio = indata.mean(axis=1)
    else:
        audio = indata.flatten()

    if audio.dtype != np.int16:
        # Float input → scale to int16
        audio = (audio * 32767).clip(-32768, 32767).astype(np.int16)

    return audio


async def list_audio_devices_async() -> list[dict]:
    """Async wrapper for device enumeration (for use in FastAPI endpoints)."""
    from backend.audio.devices import list_devices
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, list_devices)
