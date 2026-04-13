"""Recording session management for MeetScribe.

Controls the full lifecycle of a recording:
  idle → recording → paused → processing → complete

Handles:
  - Start/stop/pause from REST API
  - Raw audio buffering in memory (ephemeral per Decree 356)
  - Optional WAV save to disk (only if consent_recording=True)
  - Auto-stop after silence timeout
  - Crash-recovery WAV checkpoints (every 30s, if consent)
  - Max duration enforcement (4 hours)

File: backend/audio/recorder.py
"""

from __future__ import annotations

import asyncio
import time
import uuid
import wave
from collections import deque
from enum import Enum
from io import BytesIO
from pathlib import Path
from typing import Optional

import numpy as np
import structlog

from backend.audio.capture import AudioCapture, SAMPLE_RATE, CHANNELS
from backend.config import settings

logger = structlog.get_logger(__name__)

MAX_DURATION_SECONDS = 4 * 60 * 60          # 4 hours hard limit
CHECKPOINT_INTERVAL_SECONDS = 30            # WAV checkpoint every 30s
SILENCE_TIMEOUT_SECONDS = 300              # Auto-stop after 5 min silence
SILENCE_THRESHOLD_RMS = 0.005             # Below this = silence


class RecordingState(str, Enum):
    IDLE = "idle"
    RECORDING = "recording"
    PAUSED = "paused"
    PROCESSING = "processing"
    COMPLETE = "complete"
    ERROR = "error"


class RecordingSession:
    """Manages a single recording session from start to stop.

    One RecordingSession per meeting. The Orchestrator creates and owns it.
    """

    def __init__(
        self,
        meeting_id: str,
        system_device_id: Optional[int] = None,
        mic_device_id: Optional[int] = None,
        consent_recording: bool = False,
        silence_timeout: int = SILENCE_TIMEOUT_SECONDS,
    ):
        self.meeting_id = meeting_id
        self.consent_recording = consent_recording
        self.silence_timeout = silence_timeout

        self.state = RecordingState.IDLE
        self.started_at: Optional[float] = None
        self.ended_at: Optional[float] = None
        self.duration_seconds: int = 0

        # Audio buffer (ephemeral — destroyed after transcript committed)
        self._audio_buffer: deque[bytes] = deque()
        self._buffer_lock = asyncio.Lock()

        # Capture backend
        self._capture = AudioCapture(
            system_device_id=system_device_id,
            mic_device_id=mic_device_id,
        )

        # Queues for downstream consumers (ASR, diarization)
        self._chunk_queues: list[asyncio.Queue[bytes]] = []

        # Background tasks
        self._record_task: Optional[asyncio.Task] = None
        self._checkpoint_task: Optional[asyncio.Task] = None
        self._silence_task: Optional[asyncio.Task] = None

        self._last_audio_time: float = time.time()
        self._paused_duration: float = 0.0
        self._pause_start: Optional[float] = None

        self.wav_path: Optional[Path] = None

    # ── Public API ────────────────────────────────────────────────────────

    async def start(self) -> None:
        """Begin capturing audio."""
        if self.state not in (RecordingState.IDLE,):
            raise RuntimeError(f"Cannot start from state {self.state}")

        self.started_at = time.time()
        self.state = RecordingState.RECORDING

        await self._capture.start()

        self._record_task = asyncio.create_task(
            self._record_loop(), name=f"record-{self.meeting_id}"
        )

        if self.consent_recording:
            self._checkpoint_task = asyncio.create_task(
                self._checkpoint_loop(), name=f"checkpoint-{self.meeting_id}"
            )

        if self.silence_timeout > 0:
            self._silence_task = asyncio.create_task(
                self._silence_monitor(), name=f"silence-{self.meeting_id}"
            )

        logger.info(
            "Recording started",
            meeting_id=self.meeting_id,
            consent_recording=self.consent_recording,
        )

    async def pause(self) -> None:
        """Pause audio capture (buffer is retained)."""
        if self.state != RecordingState.RECORDING:
            return
        self.state = RecordingState.PAUSED
        self._pause_start = time.time()
        await self._capture.stop()
        logger.info("Recording paused", meeting_id=self.meeting_id)

    async def resume(self) -> None:
        """Resume a paused recording."""
        if self.state != RecordingState.PAUSED:
            return
        if self._pause_start:
            self._paused_duration += time.time() - self._pause_start
        self.state = RecordingState.RECORDING
        await self._capture.start()
        logger.info("Recording resumed", meeting_id=self.meeting_id)

    async def stop(self) -> bytes:
        """Stop capture and return the full audio as bytes (WAV).

        Returns:
            Raw WAV bytes (16-bit PCM, mono, 16kHz).
            Empty bytes if no audio was captured.
        """
        if self.state not in (RecordingState.RECORDING, RecordingState.PAUSED):
            return b""

        self.ended_at = time.time()
        self.state = RecordingState.PROCESSING

        # Stop all tasks
        await self._capture.stop()
        for task in [self._record_task, self._checkpoint_task, self._silence_task]:
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        self.duration_seconds = int(
            (self.ended_at - self.started_at) - self._paused_duration
        )

        # Assemble WAV from buffer
        wav_bytes = self._assemble_wav()

        # Save final WAV to disk if consent given
        if self.consent_recording and wav_bytes:
            self.wav_path = await self._save_wav(wav_bytes, checkpoint=False)

        # Decree 356: destroy in-memory audio buffer
        async with self._buffer_lock:
            self._audio_buffer.clear()

        logger.info(
            "Recording stopped",
            meeting_id=self.meeting_id,
            duration_seconds=self.duration_seconds,
            wav_saved=self.wav_path is not None,
        )

        return wav_bytes

    def add_chunk_consumer(self) -> asyncio.Queue[bytes]:
        """Register a downstream consumer (ASR engine, diarization).

        Returns a queue that receives every captured audio chunk.
        """
        q: asyncio.Queue[bytes] = asyncio.Queue(maxsize=500)
        self._chunk_queues.append(q)
        return q

    def get_levels(self) -> dict:
        return self._capture.get_levels()

    @property
    def elapsed_seconds(self) -> float:
        if self.started_at is None:
            return 0.0
        end = self.ended_at or time.time()
        return (end - self.started_at) - self._paused_duration

    # ── Internal loops ───────────────────────────────────────────────────

    async def _record_loop(self) -> None:
        """Main capture loop — reads chunks and fans out to consumers."""
        try:
            async for chunk in self._capture.stream():
                if self.state == RecordingState.PAUSED:
                    continue

                # Enforce max duration
                if self.elapsed_seconds >= MAX_DURATION_SECONDS:
                    logger.warning(
                        "Max recording duration reached, stopping",
                        meeting_id=self.meeting_id,
                    )
                    asyncio.create_task(self.stop())
                    break

                # Buffer for WAV assembly
                async with self._buffer_lock:
                    self._audio_buffer.append(chunk)

                # Update silence timer
                rms = _compute_rms(chunk)
                if rms > SILENCE_THRESHOLD_RMS:
                    self._last_audio_time = time.time()

                # Fan out to all downstream consumers
                for q in self._chunk_queues:
                    try:
                        q.put_nowait(chunk)
                    except asyncio.QueueFull:
                        pass  # Slow consumer — drop chunk

        except asyncio.CancelledError:
            pass
        except Exception as exc:
            logger.error("Record loop error", error=str(exc), meeting_id=self.meeting_id)
            self.state = RecordingState.ERROR

    async def _checkpoint_loop(self) -> None:
        """Save WAV checkpoint every 30s for crash recovery."""
        try:
            while True:
                await asyncio.sleep(CHECKPOINT_INTERVAL_SECONDS)
                if self.state != RecordingState.RECORDING:
                    continue
                async with self._buffer_lock:
                    wav_bytes = self._assemble_wav(locked=True)
                if wav_bytes:
                    await self._save_wav(wav_bytes, checkpoint=True)
        except asyncio.CancelledError:
            pass

    async def _silence_monitor(self) -> None:
        """Auto-stop after silence_timeout seconds of silence."""
        try:
            while True:
                await asyncio.sleep(10)
                if self.state != RecordingState.RECORDING:
                    continue
                silence_duration = time.time() - self._last_audio_time
                if silence_duration >= self.silence_timeout:
                    logger.info(
                        "Auto-stopping due to silence",
                        silence_seconds=int(silence_duration),
                        meeting_id=self.meeting_id,
                    )
                    asyncio.create_task(self.stop())
                    break
        except asyncio.CancelledError:
            pass

    # ── WAV helpers ──────────────────────────────────────────────────────

    def _assemble_wav(self, locked: bool = False) -> bytes:
        """Assemble all buffered PCM chunks into a WAV file in memory."""
        pcm = b"".join(self._audio_buffer)
        if not pcm:
            return b""

        buf = BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(2)       # int16 = 2 bytes
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(pcm)

        return buf.getvalue()

    async def _save_wav(self, wav_bytes: bytes, checkpoint: bool) -> Optional[Path]:
        """Write WAV bytes to disk (only with consent_recording=True)."""
        settings.recordings_dir.mkdir(parents=True, exist_ok=True)
        suffix = "_checkpoint" if checkpoint else ""
        path = settings.recordings_dir / f"{self.meeting_id}{suffix}.wav"

        def _write():
            path.write_bytes(wav_bytes)

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _write)
        logger.debug("WAV saved", path=str(path), checkpoint=checkpoint)
        return path


def _compute_rms(chunk: bytes) -> float:
    """Compute RMS amplitude of a PCM int16 chunk (0.0 – 1.0)."""
    if not chunk:
        return 0.0
    audio = np.frombuffer(chunk, dtype=np.int16).astype(np.float32)
    return float(np.sqrt(np.mean(audio ** 2))) / 32768.0
