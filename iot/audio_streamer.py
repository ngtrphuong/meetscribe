"""IoT Audio Streamer — Raspberry Pi / embedded device audio sender.

Captures microphone audio on IoT devices (Raspberry Pi, etc.) and
streams raw PCM to the MeetScribe backend WebSocket endpoint.

Receives transcript segments back from the server.

Usage:
    python iot/audio_streamer.py --server ws://192.168.1.100:9876 --meeting-id <id>

Requirements:
    pip install sounddevice websockets numpy
"""

from __future__ import annotations

import argparse
import asyncio
import sys

import numpy as np
import sounddevice as sd
import websockets

SAMPLE_RATE = 16_000
CHANNELS = 1
DTYPE = "int16"
CHUNK_DURATION = 0.1     # 100ms per chunk
CHUNK_SAMPLES = int(SAMPLE_RATE * CHUNK_DURATION)


async def stream_audio(server_url: str, meeting_id: str, device_id: int = None) -> None:
    """Stream microphone audio to MeetScribe WebSocket server.

    Receives transcript segments back and prints them.
    """
    ws_url = f"{server_url}/ws/audio/{meeting_id}"
    print(f"[IoT] Connecting to {ws_url}", flush=True)

    # Audio queue from sounddevice callback
    audio_queue: asyncio.Queue[bytes] = asyncio.Queue(maxsize=200)
    loop = asyncio.get_event_loop()

    def callback(indata: np.ndarray, frames: int, time_info, status):
        if status:
            print(f"[IoT] Audio status: {status}", file=sys.stderr)
        # Mix to mono int16
        if indata.ndim > 1:
            audio = indata.mean(axis=1)
        else:
            audio = indata.flatten()
        if audio.dtype != np.int16:
            audio = (audio * 32767).clip(-32768, 32767).astype(np.int16)
        try:
            loop.call_soon_threadsafe(audio_queue.put_nowait, audio.tobytes())
        except asyncio.QueueFull:
            pass

    stream = sd.InputStream(
        samplerate=SAMPLE_RATE,
        channels=CHANNELS,
        dtype=DTYPE,
        blocksize=CHUNK_SAMPLES,
        device=device_id,
        callback=callback,
    )
    stream.start()
    print("[IoT] Microphone open. Streaming audio…", flush=True)

    async with websockets.connect(ws_url) as ws:
        async def send_audio():
            while True:
                chunk = await audio_queue.get()
                await ws.send(chunk)

        async def receive_transcripts():
            import json
            async for message in ws:
                try:
                    data = json.loads(message)
                    if data.get("type") == "segment":
                        seg = data["data"]
                        print(
                            f"[{seg.get('speaker', 'Speaker')}] "
                            f"[{seg.get('start_time', 0.0):.1f}s] "
                            f"{seg.get('text', '')}",
                            flush=True,
                        )
                    elif data.get("type") == "status":
                        print(f"[Status] {data['data'].get('state')} — {data['data'].get('message', '')}", flush=True)
                except Exception:
                    pass

        await asyncio.gather(send_audio(), receive_transcripts())

    stream.stop()
    stream.close()


def main():
    parser = argparse.ArgumentParser(description="MeetScribe IoT Audio Streamer")
    parser.add_argument("--server", default="ws://localhost:9876", help="MeetScribe WebSocket server URL")
    parser.add_argument("--meeting-id", required=True, help="Meeting ID to stream to")
    parser.add_argument("--device", type=int, default=None, help="Microphone device ID")
    args = parser.parse_args()

    try:
        asyncio.run(stream_audio(args.server, args.meeting_id, args.device))
    except KeyboardInterrupt:
        print("\n[IoT] Stopped.", flush=True)


if __name__ == "__main__":
    main()
