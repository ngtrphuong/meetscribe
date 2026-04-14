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


def _portaudio_available() -> bool:
    """Check if PortAudio (sounddevice) library is available."""
    try:
        import sounddevice as sd
        sd.query_devices()
        return True
    except (ImportError, OSError):
        return False


def _pulseaudio_available() -> bool:
    """Check if PulseAudio parec command is available."""
    import shutil
    return shutil.which("parec") is not None


def create_audio_capture(
    system_device_id: Optional[int] = None,
    mic_device_id: Optional[int] = None,
    chunk_duration: float = CHUNK_DURATION,
) -> "AudioCaptureBackend":
    """Factory that creates an available AudioCapture backend.

    Tries PortAudio first (sounddevice), falls back to PulseAudio (parec).
    Raises RuntimeError if neither is available.
    """
    if _portaudio_available():
        return AudioCapture(
            system_device_id=system_device_id,
            mic_device_id=mic_device_id,
            chunk_duration=chunk_duration,
        )

    if _pulseaudio_available():
        return PulseAudioCapture(
            source_name=None,  # uses default PulseAudio source
            chunk_duration=chunk_duration,
        )

    raise RuntimeError(
        "No audio backend available. Install PortAudio (libportaudio2) "
        "or ensure PulseAudio and parec are available."
    )


def create_composite_audio_capture(
    mic_source: Optional[str] = None,
    udp_url: Optional[str] = None,
    mix_weights: tuple[float, float] = (1.0, 1.0),
    chunk_duration: float = CHUNK_DURATION,
) -> "CompositePulseAudioCapture":
    """Create a composite audio capture that mixes multiple sources.

    Args:
        mic_source: PulseAudio source name for microphone.
                   Default: "RDPSource" (WSLg mic), or None for PA default.
        udp_url: UDP URL to receive Windows desktop audio, e.g. "udp://0.0.0.0:20000".
                 If None, captures mic only.
        mix_weights: (mic_weight, udp_weight) for sox -m volume adjustment.
                    Set to (0, 1) for UDP-only, (1, 0) for mic-only.
        chunk_duration: seconds per chunk (default 0.1 → 1600 samples = 3200 bytes)
    """
    return CompositePulseAudioCapture(
        mic_source=mic_source,
        udp_url=udp_url,
        mix_weights=mix_weights,
        chunk_duration=chunk_duration,
    )


class CompositePulseAudioCapture:
    """Captures and mixes audio from multiple sources using sox.

    Supports combining:
      - Microphone (PulseAudio via parec), e.g. RDPSource on WSLg
      - Windows desktop audio (received via UDP from ffmpeg/dshow on Windows)

    Pipeline (mic + UDP):
      bash -l -c "parec -d 'RDPSource' ... | sox -m <(parec ...) <(ffmpeg ...) -t raw -"

    Pipeline (mic only, no UDP):
      bash -l -c "parec ... | sox ... -t raw -"

    Output: raw PCM int16 mono 16kHz chunks, matching AudioCapture format.
    """

    def __init__(
        self,
        mic_source: Optional[str] = None,
        udp_url: Optional[str] = None,
        mix_weights: tuple[float, float] = (1.0, 1.0),
        chunk_duration: float = CHUNK_DURATION,
    ):
        self.mic_source = mic_source or "RDPSource"
        self.udp_url = udp_url
        self.mic_weight, self.udp_weight = mix_weights
        self.chunk_duration = chunk_duration
        self.chunk_bytes = int(SAMPLE_RATE * chunk_duration) * 2  # int16

        self._queue: asyncio.Queue[bytes] = asyncio.Queue(maxsize=200)
        self._running = False
        self._proc: Optional[asyncio.subprocess.Process] = None
        self._reader_task: Optional[asyncio.Task] = None
        self._cleanup_tasks: list[asyncio.Task] = []

        # Level meters (0.0 – 1.0)
        self.mic_level: float = 0.0
        self.udp_level: float = 0.0

    async def start(self) -> None:
        """Start the composite audio capture pipeline."""
        if self._running:
            return

        import shutil
        for cmd in ["parec", "sox", "ffmpeg"]:
            if not shutil.which(cmd):
                raise RuntimeError(f"{cmd} not found — install {cmd}")

        self._running = True

        # Build the sox -m pipeline command
        mic_dev = shutil.which("parec")
        sox_bin = shutil.which("sox")
        ffmpeg_bin = shutil.which("ffmpeg")

        if self.udp_url:
            # Composite: mic + UDP
            # Correct sox -m syntax: -r/.../.../.../ flags go BEFORE each input
            # Process substitution <(...) creates a FIFO; sox reads from it as raw PCM
            pipeline = (
                f"bash -c '"
                f"{sox_bin} -V0 -m "
                f"-r {SAMPLE_RATE} -e signed -b 16 -c {CHANNELS} -t raw "
                f"<({mic_dev} -d '{self.mic_source}' -r {SAMPLE_RATE} -e s16le -c {CHANNELS} 2>/dev/null) "
                f"-r {SAMPLE_RATE} -e signed -b 16 -c {CHANNELS} -t raw "
                f"<({ffmpeg_bin} -nostdin -fflags nobuffer -f s16le -ac 1 -ar {SAMPLE_RATE} "
                f"-i \\\"{self.udp_url}\\\" -f s16le -ac 1 - 2>/dev/null) "
                f"-v {self.mic_weight} -v {self.udp_weight} "
                f"-r {SAMPLE_RATE} -e signed -b 16 -c {CHANNELS} -t raw -"
                f"'"
            )
        else:
            # Mic only (no UDP) — pipe parec output through sox for format safety
            pipeline = (
                f"{mic_dev} -d '{self.mic_source}' -r {SAMPLE_RATE} -e s16le -c {CHANNELS} 2>/dev/null | "
                f"{sox_bin} -V0 -r {SAMPLE_RATE} -e signed -b 16 -c {CHANNELS} -t raw - "
                f"-r {SAMPLE_RATE} -e signed -b 16 -c {CHANNELS} -t raw -"
            )

        try:
            self._proc = await asyncio.create_subprocess_shell(
                pipeline,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except FileNotFoundError as exc:
            raise RuntimeError(f"bash not available: {exc}")

        self._reader_task = asyncio.create_task(self._read_loop())

        logger.info(
            "Composite audio capture started",
            mic=self.mic_source,
            udp=self.udp_url,
            weights=(self.mic_weight, self.udp_weight),
        )

    async def _read_loop(self) -> None:
        """Read raw PCM from sox stdout, push to queue as chunks."""
        loop = asyncio.get_event_loop()
        buffer = b""

        try:
            while True:
                if self._proc is None or self._proc.stdout is None:
                    break

                data = await self._proc.stdout.read(self.chunk_bytes * 4)
                if not data:
                    # EOF — process ended
                    break

                buffer += data

                # Yield complete chunks
                while len(buffer) >= self.chunk_bytes:
                    chunk = buffer[:self.chunk_bytes]
                    buffer = buffer[self.chunk_bytes:]

                    # Update mic level (approx from overall RMS)
                    audio = np.frombuffer(chunk, dtype=np.int16).astype(np.float32)
                    rms = float(np.sqrt(np.mean(audio ** 2))) / 32768.0
                    self.mic_level = min(rms * 4, 1.0)

                    try:
                        loop.call_soon_threadsafe(
                            self._queue.put_nowait, chunk
                        )
                    except asyncio.QueueFull:
                        pass

        except asyncio.CancelledError:
            pass
        except Exception as exc:
            logger.error("Composite capture read loop error", error=str(exc))
        finally:
            self._running = False

    async def stop(self) -> None:
        """Stop the pipeline and cleanup."""
        self._running = False

        if self._reader_task:
            self._reader_task.cancel()
            try:
                await self._reader_task
            except asyncio.CancelledError:
                pass
            self._reader_task = None

        for t in self._cleanup_tasks:
            t.cancel()
            try:
                await t
            except asyncio.CancelledError:
                pass
        self._cleanup_tasks.clear()

        if self._proc:
            try:
                self._proc.terminate()
                try:
                    await asyncio.wait_for(self._proc.wait(), timeout=2.0)
                except asyncio.TimeoutError:
                    self._proc.kill()
                    await self._proc.wait()
                except ProcessLookupError:
                    pass
            except Exception:
                pass
            finally:
                self._proc = None

        logger.info("Composite audio capture stopped")

    async def stream(self) -> AsyncIterator[bytes]:
        """Async generator yielding PCM chunks while capture is running."""
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
            "system": round(self.udp_level, 3),
            "mic": round(self.mic_level, 3),
        }

    @property
    def is_running(self) -> bool:
        return self._running


class PulseAudioCapture:
    """Captures audio from a PulseAudio source using parec + sox pipeline.

    This is a fallback for environments (WSL2 with WSLg) where PortAudio
    is not available but PulseAudio is running.

    Pipeline: parec (capture from PulseAudio) | sox (convert) → raw PCM

    Audio chunks match the same format as AudioCapture:
    16-bit PCM, mono, 16kHz.
    """

    def __init__(
        self,
        source_name: Optional[str] = None,
        chunk_duration: float = CHUNK_DURATION,
    ):
        """
        Args:
            source_name: PulseAudio source name (e.g. "RDPSource", "RDPSink.monitor").
                        None = default PulseAudio source.
            chunk_duration: seconds per chunk (default 0.1 → 1600 samples = 3200 bytes)
        """
        self.source_name = source_name
        self.chunk_duration = chunk_duration
        self.chunk_bytes = int(SAMPLE_RATE * chunk_duration) * 2  # int16 = 2 bytes

        self._queue: asyncio.Queue[bytes] = asyncio.Queue(maxsize=200)
        self._running = False
        self._proc: Optional[asyncio.subprocess.Process] = None
        self._reader_task: Optional[asyncio.Task] = None

        # Level meter (0.0 – 1.0)
        self.mic_level: float = 0.0

    async def start(self) -> None:
        """Start parec | sox pipeline for PulseAudio capture."""
        if self._running:
            return

        import shutil
        if not shutil.which("parec"):
            raise RuntimeError("parec not found — install pulseaudio-utils")
        if not shutil.which("sox"):
            raise RuntimeError("sox not found — install sox")

        self._running = True

        # parec: capture from PulseAudio source as S16LE 16kHz mono.
        # sox: convert (in case source has different rate/channels) to
        #      signed 16-bit little-endian 16kHz mono raw PCM.
        source_arg = str(self.source_name) if self.source_name else ""
        parec_cmd = ["parec", "-d", source_arg,
                     "-r", str(SAMPLE_RATE),
                     "-e", "s16le",
                     "-c", str(CHANNELS)]

        sox_cmd = ["sox", "-V0",
                   "-r", str(SAMPLE_RATE),
                   "-e", "signed",
                   "-b", "16",
                   "-c", "1",
                   "-t", "raw", "pipe:0",
                   "-r", str(SAMPLE_RATE),
                   "-e", "signed",
                   "-b", "16",
                   "-c", "1",
                   "-t", "raw", "-"]

        try:
            # Use shell pipeline: parec | sox → raw PCM
            # parec: capture from PulseAudio source at 16kHz S16LE mono
            # sox: resample/convert to exact target format, output raw PCM
            # Correct sox syntax: sox [input opts] - [output opts] -
            # (first dash = stdin/stdout as raw, second dash = output to stdout as raw)
            pipeline = (
                f"parec -d '{source_arg}' -r {SAMPLE_RATE} -e s16le -c {CHANNELS} 2>/dev/null | "
                f"sox -V0 -r {SAMPLE_RATE} -e signed -b 16 -c {CHANNELS} -t raw - "
                f"-r {SAMPLE_RATE} -e signed -b 16 -c {CHANNELS} -t raw -"
            )
            self._proc = await asyncio.create_subprocess_shell(
                pipeline,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except FileNotFoundError as exc:
            raise RuntimeError(f"parec or sox not available: {exc}")

        self._reader_task = asyncio.create_task(self._read_loop())

        import structlog
        structlog.get_logger(__name__).info(
            "PulseAudio capture started",
            source=self.source_name or "default",
        )

    async def _read_loop(self) -> None:
        """Read raw PCM from sox stdout, push to queue as chunks."""
        loop = asyncio.get_event_loop()
        buffer = b""

        try:
            while True:
                if self._proc is None or self._proc.stdout is None:
                    break

                data = await self._proc.stdout.read(self.chunk_bytes * 4)
                if not data:
                    # EOF — process ended
                    break

                buffer += data

                # Yield complete chunks
                while len(buffer) >= self.chunk_bytes:
                    chunk = buffer[:self.chunk_bytes]
                    buffer = buffer[self.chunk_bytes:]

                    # Update level meter
                    audio = np.frombuffer(chunk, dtype=np.int16).astype(np.float32)
                    rms = float(np.sqrt(np.mean(audio ** 2))) / 32768.0
                    self.mic_level = min(rms * 4, 1.0)

                    try:
                        loop.call_soon_threadsafe(
                            self._queue.put_nowait, chunk
                        )
                    except asyncio.QueueFull:
                        pass

        except asyncio.CancelledError:
            pass
        except Exception as exc:
            import structlog
            structlog.get_logger(__name__).error(
                "PulseAudio read loop error", error=str(exc)
            )
        finally:
            self._running = False

    async def stop(self) -> None:
        """Stop the parec/sox pipeline and cleanup."""
        self._running = False

        if self._reader_task:
            self._reader_task.cancel()
            try:
                await self._reader_task
            except asyncio.CancelledError:
                pass
            self._reader_task = None

        if self._proc:
            try:
                self._proc.terminate()
                try:
                    await asyncio.wait_for(self._proc.wait(), timeout=2.0)
                except asyncio.TimeoutError:
                    self._proc.kill()
                    await self._proc.wait()
                except ProcessLookupError:
                    pass  # already exited
            except Exception:
                pass
            finally:
                self._proc = None

        import structlog
        structlog.get_logger(__name__).info("PulseAudio capture stopped")

    async def stream(self) -> AsyncIterator[bytes]:
        """Async generator yielding PCM chunks while capture is running."""
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
            "system": 0.0,  # system audio not captured separately in PA mode
            "mic": round(self.mic_level, 3),
        }

    @property
    def is_running(self) -> bool:
        return self._running


# Type alias for the common capture interface
AudioCaptureBackend = PulseAudioCapture | AudioCapture
