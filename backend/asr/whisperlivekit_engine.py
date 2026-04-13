"""WhisperLiveKit — Simultaneous speech-to-text with web frontend.

GitHub: QuentinFuxa/WhisperLiveKit
Features:
- SimulStreaming (AlignAtt) + LocalAgreement streaming policies
- Multiple ASR backends: faster-whisper, mlx-whisper, voxtral
- Built-in speaker diarization
- Web UI with WebSocket audio streaming
- LoRA adapter support for domain adaptation

Install: pip install whisperlivekit
"""

from __future__ import annotations

import asyncio
import subprocess
from typing import AsyncIterator, Optional

from backend.asr.base import ASREngine, TranscriptSegment


class WhisperLiveKitEngine(ASREngine):
    """WhisperLiveKit — web-based simultaneous streaming ASR.

    Runs as a separate server process with its own web UI.
    MeetScribe can either:
    1. Use it as a standalone streaming frontend (web UI on its own port)
    2. Wrap its output via WebSocket and feed into MeetScribe pipeline

    Best for: users who want a quick browser-based streaming setup.
    """

    def __init__(self):
        self.process: Optional[subprocess.Popen] = None
        self.host = "localhost"
        self.port = 8089

    async def initialize(self, config: dict) -> None:
        self.host = config.get("host", "localhost")
        self.port = config.get("port", 8089)
        self.model = config.get("model", "large-v3")
        self.language = config.get("language", "vi")
        self.diarization = config.get("diarization", False)
        self.streaming_strategy = config.get("strategy", "simulstreaming")

        # Start WhisperLiveKit as subprocess
        cmd = [
            "wlk",
            "--host", self.host,
            "--port", str(self.port),
            "--model", self.model,
            "--language", self.language,
            "--strategy", self.streaming_strategy,
        ]
        if self.diarization:
            cmd.append("--diarization")

        self.process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        await asyncio.sleep(3)  # Wait for server startup

    async def transcribe_stream(
        self, audio_chunks: AsyncIterator[bytes]
    ) -> AsyncIterator[TranscriptSegment]:
        """Connect to WhisperLiveKit WebSocket and relay results."""
        import websockets

        uri = f"ws://{self.host}:{self.port}/ws"
        async with websockets.connect(uri) as ws:
            async for chunk in audio_chunks:
                await ws.send(chunk)
                try:
                    response = await asyncio.wait_for(ws.recv(), timeout=0.2)
                    import json
                    data = json.loads(response)
                    if data.get("text"):
                        yield TranscriptSegment(
                            text=data["text"],
                            start_time=data.get("start", 0.0),
                            end_time=data.get("end", 0.0),
                            confidence=0.9,
                            language=self.language,
                            is_final=data.get("is_final", True),
                            speaker=data.get("speaker"),
                            source="live",
                        )
                except asyncio.TimeoutError:
                    continue

    async def transcribe_file(
        self, file_path: str, hotwords: Optional[list[str]] = None
    ) -> list[TranscriptSegment]:
        raise NotImplementedError(
            "WhisperLiveKit is streaming-only. Use faster-whisper or VibeVoice for file transcription."
        )

    async def shutdown(self) -> None:
        if self.process:
            self.process.terminate()
            self.process.wait()
            self.process = None

    @property
    def capabilities(self) -> dict:
        return {
            "streaming": True,
            "languages": ["vi", "en", "fr", "de", "ja", "ko", "zh", "es", "99+ via Whisper"],
            "gpu_required": True,
            "gpu_vram_mb": 10000,
            "has_diarization": self.diarization if hasattr(self, "diarization") else False,
            "has_timestamps": True,
            "has_punctuation": False,
            "has_web_ui": True,
            "model_name": "WhisperLiveKit (SimulStreaming)",
        }
