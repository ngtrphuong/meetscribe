"""WebSocket endpoints for MeetScribe real-time streaming.

Two endpoints per CLAUDE.md §7.2:

  ws://.../ws/transcript/{meeting_id}
    → Server pushes transcript segments, diarization, status, level meters

  ws://.../ws/audio/{meeting_id}
    → IoT/remote clients push raw PCM audio; server returns transcripts

Message format (server → client):
  { "type": "segment",      "data": TranscriptSegment }
  { "type": "diarization",  "data": { "speaker", "start", "end" } }
  { "type": "status",       "data": { "state": str, "message": str } }
  { "type": "level",        "data": { "system": float, "mic": float } }
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import structlog
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = structlog.get_logger(__name__)

router = APIRouter()

# Global connection manager (meeting_id → list of WebSocket connections)
_connections: dict[str, list[WebSocket]] = {}


class ConnectionManager:
    """Manages active WebSocket connections per meeting."""

    def connect(self, meeting_id: str, ws: WebSocket) -> None:
        if meeting_id not in _connections:
            _connections[meeting_id] = []
        _connections[meeting_id].append(ws)
        logger.debug("WS connected", meeting_id=meeting_id, total=len(_connections[meeting_id]))

    def disconnect(self, meeting_id: str, ws: WebSocket) -> None:
        if meeting_id not in _connections:
            return
        conn_list = _connections[meeting_id]
        if ws in conn_list:
            conn_list.remove(ws)
        if not conn_list:
            del _connections[meeting_id]
        logger.debug("WS disconnected", meeting_id=meeting_id, remaining=len(conn_list))

    async def broadcast(self, meeting_id: str, message: dict) -> None:
        """Send a message to all clients subscribed to a meeting."""
        conns = _connections.get(meeting_id, [])
        if not conns:
            return
        payload = json.dumps(message, ensure_ascii=False)
        dead: list[WebSocket] = []
        for ws in conns:
            try:
                await ws.send_text(payload)
            except Exception:
                dead.append(ws)
        # Remove dead connections outside the iteration loop
        for ws in dead:
            if ws in _connections.get(meeting_id, []):
                _connections[meeting_id].remove(ws)
        # Clean up empty lists
        if meeting_id in _connections and not _connections[meeting_id]:
            del _connections[meeting_id]

    async def send_segment(self, meeting_id: str, segment_dict: dict) -> None:
        await self.broadcast(meeting_id, {"type": "segment", "data": segment_dict})

    async def send_status(self, meeting_id: str, state: str, message: str = "") -> None:
        await self.broadcast(meeting_id, {"type": "status", "data": {"state": state, "message": message}})

    async def send_level(self, meeting_id: str, system: float, mic: float) -> None:
        await self.broadcast(meeting_id, {"type": "level", "data": {"system": system, "mic": mic}})

    async def send_diarization(self, meeting_id: str, speaker: str, start: float, end: float) -> None:
        await self.broadcast(meeting_id, {
            "type": "diarization",
            "data": {"speaker": speaker, "start": start, "end": end},
        })


manager = ConnectionManager()


@router.websocket("/ws/transcript/{meeting_id}")
async def transcript_ws(websocket: WebSocket, meeting_id: str):
    """Subscribe to real-time transcript, status, and level events for a meeting.

    The server pushes all events; clients typically only receive (no upload).
    """
    await websocket.accept()
    manager.connect(meeting_id, websocket)

    try:
        # Send initial status
        from backend.pipeline.orchestrator import get_orchestrator
        orch = get_orchestrator()
        state = orch.get_meeting_state(meeting_id)
        await websocket.send_text(
            json.dumps({"type": "status", "data": {"state": state, "message": "connected"}})
        )

        # Keep alive — wait for disconnect
        while True:
            try:
                # Echo heartbeats; disconnect on client close
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30)
                if data == "ping":
                    await websocket.send_text(json.dumps({"type": "pong"}))
            except asyncio.TimeoutError:
                # Send keepalive ping
                try:
                    await websocket.send_text(json.dumps({"type": "ping"}))
                except Exception:
                    break

    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logger.error("Transcript WS error", meeting_id=meeting_id, error=str(exc))
    finally:
        manager.disconnect(meeting_id, websocket)


@router.websocket("/ws/audio/{meeting_id}")
async def audio_ws(websocket: WebSocket, meeting_id: str):
    """Receive raw PCM audio from IoT/remote clients and stream transcripts back.

    Client sends: raw PCM bytes (16-bit, 16kHz, mono)
    Server sends: transcript segment messages
    """
    await websocket.accept()
    logger.info("IoT audio stream connected", meeting_id=meeting_id)

    try:
        from backend.pipeline.orchestrator import get_orchestrator
        orch = get_orchestrator()
        audio_queue: asyncio.Queue[bytes] = asyncio.Queue(maxsize=500)

        # Register as audio source for this meeting
        orch.register_iot_audio(meeting_id, audio_queue)

        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_bytes(), timeout=10)
                if data:
                    try:
                        audio_queue.put_nowait(data)
                    except asyncio.QueueFull:
                        pass  # Drop frames if pipeline is overloaded
            except asyncio.TimeoutError:
                # Check if meeting still active
                if not orch.is_meeting_active(meeting_id):
                    break

    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logger.error("Audio WS error", meeting_id=meeting_id, error=str(exc))
    finally:
        logger.info("IoT audio stream disconnected", meeting_id=meeting_id)
