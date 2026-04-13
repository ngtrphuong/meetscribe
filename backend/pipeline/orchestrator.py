"""Meeting pipeline orchestrator — coordinates the full meeting lifecycle.

Implements CLAUDE.md §11:
  LIVE: start audio → detect language → select ASR → start diart → stream to WS
  END:  stop audio → save WAV → unload LIVE models → load VibeVoice → reprocess
        → parse structured output → save POST segments → load LLM → summarize
        → save summary + action items → notify clients via WS

CRITICAL GPU RULES:
  - Never run LIVE and POST engines simultaneously on RTX 3090
  - Unload LIVE before loading POST
  - Raw audio destroyed after transcript committed (Decree 356)

File: backend/pipeline/orchestrator.py
"""

from __future__ import annotations

import asyncio
import datetime
import uuid
from typing import Optional

import structlog

from backend.config import settings
from backend.audio.recorder import RecordingSession, RecordingState
from backend.asr.base import TranscriptSegment
from backend.storage.models import TranscriptSegmentDB
from backend.audio.maxine_preprocessor import MaxinePreprocessor

logger = structlog.get_logger(__name__)

# Module-level singleton
_orchestrator: Optional["MeetingOrchestrator"] = None


def get_orchestrator() -> "MeetingOrchestrator":
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = MeetingOrchestrator()
    return _orchestrator


class MeetingOrchestrator:
    """Owns the full lifecycle of all active meetings."""

    def __init__(self):
        self._sessions: dict[str, MeetingSession] = {}

    async def start_meeting(
        self,
        title: Optional[str] = None,
        system_device_id: Optional[int] = None,
        mic_device_id: Optional[int] = None,
        language: str = "vi",
        hotwords: Optional[list[str]] = None,
        consent_recording: bool = False,
        consent_voiceprint: bool = False,
        template_name: str = "general_vi",
        llm_provider: str = "ollama",
        silence_timeout: int = 300,
    ) -> str:
        """Start a new meeting recording session.

        Returns the meeting_id.
        """
        from backend.storage.repository import create_meeting
        from backend.asr.language_router import LanguageRouter

        # Create DB record
        auto_title = title or f"Cuộc họp {datetime.datetime.now().strftime('%d/%m/%Y %H:%M')}"
        meeting = await create_meeting(
            title=auto_title,
            language=language,
            asr_live_engine=settings.asr_live_engine,
            asr_post_engine=settings.asr_post_engine,
            llm_provider=llm_provider,
            template_name=template_name,
            consent_recording=consent_recording,
            consent_voiceprint=consent_voiceprint,
        )

        # Create session
        session = MeetingSession(
            meeting_id=meeting.id,
            language_hint=language,
            hotwords=hotwords or [],
            consent_recording=consent_recording,
            consent_voiceprint=consent_voiceprint,
            template_name=template_name,
            llm_provider=llm_provider,
        )

        self._sessions[meeting.id] = session

        # Start in background
        asyncio.create_task(
            session.run(
                system_device_id=system_device_id,
                mic_device_id=mic_device_id,
                silence_timeout=silence_timeout,
            ),
            name=f"session-{meeting.id}",
        )

        return meeting.id

    async def stop_meeting(self, meeting_id: str) -> None:
        session = self._sessions.get(meeting_id)
        if session:
            await session.stop()

    async def pause_meeting(self, meeting_id: str) -> None:
        session = self._sessions.get(meeting_id)
        if session and session.recorder:
            await session.recorder.pause()

    async def resume_meeting(self, meeting_id: str) -> None:
        session = self._sessions.get(meeting_id)
        if session and session.recorder:
            await session.recorder.resume()

    def is_meeting_active(self, meeting_id: str) -> bool:
        session = self._sessions.get(meeting_id)
        if not session:
            return False
        return session.recorder is not None and session.recorder.state in (
            RecordingState.RECORDING, RecordingState.PAUSED
        )

    def get_meeting_state(self, meeting_id: str) -> Optional[str]:
        session = self._sessions.get(meeting_id)
        if not session:
            return None
        if session.recorder:
            return session.recorder.state.value
        return "idle"

    def register_iot_audio(self, meeting_id: str, audio_queue: asyncio.Queue) -> None:
        session = self._sessions.get(meeting_id)
        if session:
            session.iot_queues.append(audio_queue)


class MeetingSession:
    """Manages one meeting: recording → LIVE ASR → POST ASR → summarization."""

    def __init__(
        self,
        meeting_id: str,
        language_hint: str,
        hotwords: list[str],
        consent_recording: bool,
        consent_voiceprint: bool,
        template_name: str,
        llm_provider: str,
    ):
        self.meeting_id = meeting_id
        self.language_hint = language_hint
        self.hotwords = hotwords
        self.consent_recording = consent_recording
        self.consent_voiceprint = consent_voiceprint
        self.template_name = template_name
        self.llm_provider = llm_provider

        self.recorder: Optional[RecordingSession] = None
        self.live_engine = None
        self.diarizer = None
        self.iot_queues: list[asyncio.Queue] = []

        self._stop_event = asyncio.Event()

    async def run(
        self,
        system_device_id: Optional[int],
        mic_device_id: Optional[int],
        silence_timeout: int,
    ) -> None:
        """Full session lifecycle."""
        from backend.api.websocket import manager

        live_error = None
        try:
            await self._start_live_phase(system_device_id, mic_device_id, silence_timeout)
        except Exception as exc:
            logger.error("LIVE phase error", meeting_id=self.meeting_id, error=str(exc))
            live_error = exc
            await manager.send_status(self.meeting_id, "processing", f"LIVE capture unavailable ({exc}), running POST phase…")

        # POST phase always runs (even when LIVE phase failed — we still try to process any audio)
        await manager.send_status(self.meeting_id, "processing", "Running POST transcription…")
        try:
            await self._run_post_phase()
            await manager.send_status(self.meeting_id, "complete", "Meeting notes ready")
        except Exception as exc:
            logger.error("POST phase error", meeting_id=self.meeting_id, error=str(exc))
            # Mark complete even on POST failure so status doesn't stay 'recording'
            from backend.storage.repository import update_meeting
            await update_meeting(
                self.meeting_id,
                status="complete",
                ended_at=datetime.datetime.now(datetime.UTC).isoformat(),
                duration_seconds=0,
            )
            await manager.send_status(self.meeting_id, "error", f"POST failed: {exc}")

    async def _start_live_phase(
        self,
        system_device_id: Optional[int],
        mic_device_id: Optional[int],
        silence_timeout: int,
    ) -> None:
        """Set up and run LIVE recording + ASR + diarization."""
        from backend.asr.language_router import LanguageRouter
        from backend.asr.engine_factory import ASREngineFactory
        from backend.diarization.live_diarization import LiveDiarization
        from backend.api.websocket import manager

        # Create recorder
        self.recorder = RecordingSession(
            meeting_id=self.meeting_id,
            system_device_id=system_device_id,
            mic_device_id=mic_device_id,
            consent_recording=self.consent_recording,
            silence_timeout=silence_timeout,
        )

        # Fan-out queue for ASR
        asr_queue = self.recorder.add_chunk_consumer()
        # Fan-out queue for diarization
        diar_queue = self.recorder.add_chunk_consumer()

        await self.recorder.start()

        # Detect language from first 3 seconds of audio
        router = LanguageRouter()
        first_chunk = b""
        try:
            chunk = await asyncio.wait_for(asr_queue.get(), timeout=5.0)
            first_chunk = chunk
        except asyncio.TimeoutError:
            pass

        if self.language_hint != "auto":
            detected_lang = self.language_hint
        else:
            detected_lang = await router.detect_language(first_chunk)

        engine_name = router.select_live_engine(detected_lang)
        logger.info("LIVE engine selected", engine=engine_name, language=detected_lang)

        # Load LIVE ASR engine
        self.live_engine = ASREngineFactory.create(engine_name)
        await self.live_engine.initialize({"language": detected_lang if detected_lang != "mixed" else None})

        # Start diarization
        self.diarizer = LiveDiarization()
        await self.diarizer.start(diar_queue)

        # Re-inject first chunk into ASR queue for processing
        if first_chunk:
            asr_queue.put_nowait(first_chunk)

        # Start ASR streaming task
        asr_task = asyncio.create_task(
            self._stream_asr(asr_queue, manager),
            name=f"asr-{self.meeting_id}",
        )

        # Start level meter broadcast
        level_task = asyncio.create_task(
            self._broadcast_levels(manager),
            name=f"levels-{self.meeting_id}",
        )

        # Wait for stop signal
        await self._stop_event.wait()

        # Cancel all live tasks
        for task in [asr_task, level_task]:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        await self.diarizer.stop()

    async def _stream_asr(self, queue: asyncio.Queue, manager) -> None:
        """Read chunks from queue and stream through ASR engine."""
        from backend.storage.repository import insert_segment

        async def chunk_gen():
            while True:
                try:
                    chunk = await asyncio.wait_for(queue.get(), timeout=1.0)
                    yield chunk
                except asyncio.TimeoutError:
                    if self._stop_event.is_set():
                        return

        try:
            async for seg in self.live_engine.transcribe_stream(chunk_gen()):
                if not seg.text.strip():
                    continue

                # Save to DB
                db_seg = TranscriptSegmentDB(
                    meeting_id=self.meeting_id,
                    text=seg.text,
                    start_time=seg.start_time,
                    end_time=seg.end_time,
                    confidence=seg.confidence,
                    language=seg.language,
                    speaker_label=seg.speaker,
                    source="live",
                )
                await insert_segment(db_seg)

                # Push to WebSocket
                await manager.send_segment(self.meeting_id, seg.to_dict())

        except asyncio.CancelledError:
            pass
        except Exception as exc:
            logger.error("ASR stream error", error=str(exc), meeting_id=self.meeting_id)

    async def _broadcast_levels(self, manager) -> None:
        """Broadcast audio level meters every 100ms."""
        try:
            while not self._stop_event.is_set():
                if self.recorder:
                    levels = self.recorder.get_levels()
                    await manager.send_level(
                        self.meeting_id,
                        levels["system"],
                        levels["mic"],
                    )
                await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            pass

    async def stop(self) -> None:
        """Signal the session to stop and collect audio."""
        if self.recorder:
            self._wav_bytes = await self.recorder.stop()
        self._stop_event.set()

        # Unload LIVE engine to free GPU (Decree: LIVE before POST)
        if self.live_engine:
            await self.live_engine.shutdown()
            self.live_engine = None

    async def _run_post_phase(self) -> None:
        """POST: VibeVoice transcription → LLM summarization → DB save."""
        from backend.storage.repository import (
            get_transcript, delete_segments_by_source, insert_segments_bulk,
            save_summary, update_meeting,
        )
        from backend.storage.embeddings import get_embedder
        from backend.llm.summarizer import MeetingSummarizer

        meeting = await _get_meeting(self.meeting_id)
        if not meeting:
            return

        # Run POST ASR if we have audio
        wav_path = self.recorder.wav_path if self.recorder else None
        wav_bytes = getattr(self, "_wav_bytes", b"")

        post_segments: list[TranscriptSegmentDB] = []

        if wav_bytes or wav_path:
            post_segments = await self._run_post_asr(wav_bytes, wav_path)

        if post_segments:
            # Replace LIVE segments with POST segments
            await delete_segments_by_source(self.meeting_id, "live")
            await insert_segments_bulk(post_segments)

            # Build embeddings for semantic search
            try:
                embedder = get_embedder()
                await embedder.embed_meeting_segments(self.meeting_id)
            except Exception as exc:
                logger.warning("Embedding failed", error=str(exc))

        # Get final transcript for LLM
        segments_db = await get_transcript(self.meeting_id)
        asr_segments = [
            TranscriptSegment(
                text=s.text,
                start_time=s.start_time,
                end_time=s.end_time,
                confidence=s.confidence or 0.9,
                language=s.language or "vi",
                speaker=s.speaker_label,
                source=s.source,
            )
            for s in segments_db
        ]

        if not asr_segments:
            logger.warning("No segments for summarization", meeting_id=self.meeting_id)
            await update_meeting(
                self.meeting_id,
                status="complete",
                ended_at=datetime.datetime.now(datetime.UTC).isoformat(),
                duration_seconds=0,
            )
            return

        # Run LLM summarization
        summarizer = MeetingSummarizer()
        duration = self.recorder.duration_seconds if self.recorder else 0
        summary_text = await summarizer.summarize(
            segments=asr_segments,
            template_name=self.template_name,
            provider_name=self.llm_provider,
            meeting_title=meeting.title,
            started_at=meeting.started_at,
            duration_seconds=duration,
        )

        await save_summary(
            meeting_id=self.meeting_id,
            content=summary_text,
            template_name=self.template_name,
            llm_provider=self.llm_provider,
            llm_model=settings.llm_model,
        )

        # Update meeting status
        await update_meeting(
            self.meeting_id,
            status="complete",
            ended_at=datetime.datetime.now(datetime.UTC).isoformat(),
            duration_seconds=duration,
            audio_file_path=str(wav_path) if wav_path else None,
            audio_retained=bool(wav_path),
        )

        logger.info("POST phase complete", meeting_id=self.meeting_id)

    async def _run_post_asr(
        self, wav_bytes: bytes, wav_path
    ) -> list[TranscriptSegmentDB]:
        """Run VibeVoice (or fallback) on the complete audio."""
        from backend.asr.engine_factory import ASREngineFactory
        import tempfile
        import pathlib

        # Write audio to temp file if we only have bytes
        tmp_file = None
        if wav_bytes and not wav_path:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                f.write(wav_bytes)
                tmp_file = f.name
            audio_path = tmp_file
        elif wav_path:
            audio_path = str(wav_path)
        else:
            return []

        try:
            engine = ASREngineFactory.create(settings.asr_post_engine)
            await engine.initialize({"quantization": settings.vibevoice_quantization})
            asr_segments = await engine.transcribe_file(audio_path, hotwords=self.hotwords)
            await engine.shutdown()

            return [
                TranscriptSegmentDB(
                    meeting_id=self.meeting_id,
                    text=seg.text,
                    start_time=seg.start_time,
                    end_time=seg.end_time,
                    confidence=seg.confidence,
                    language=seg.language,
                    speaker_label=seg.speaker,
                    source="post",
                )
                for seg in asr_segments
                if seg.text.strip()
            ]

        except Exception as exc:
            logger.error(
                "POST ASR failed, keeping LIVE segments",
                engine=settings.asr_post_engine,
                error=str(exc),
            )
            return []

        finally:
            if tmp_file:
                pathlib.Path(tmp_file).unlink(missing_ok=True)


async def _get_meeting(meeting_id: str):
    from backend.storage.repository import get_meeting
    return await get_meeting(meeting_id)
