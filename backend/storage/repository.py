"""Database CRUD operations for MeetScribe.

All methods use the get_db() async context manager (SQLCipher / aiosqlite).
Row dictionaries from aiosqlite.Row are converted to Pydantic models.

File: backend/storage/repository.py
"""

from __future__ import annotations

import datetime
import json
import uuid
from typing import Optional

import structlog

from backend.database import get_db, audit
from backend.storage.models import (
    Meeting,
    TranscriptSegmentDB,
    Summary,
    ActionItem,
    MeetingDetail,
)

logger = structlog.get_logger(__name__)


# ── Meetings ──────────────────────────────────────────────────────────────────

async def create_meeting(
    title: str,
    language: str = "vi",
    asr_live_engine: Optional[str] = None,
    asr_post_engine: Optional[str] = None,
    llm_provider: Optional[str] = None,
    template_name: Optional[str] = None,
    consent_recording: bool = False,
    consent_voiceprint: bool = False,
) -> Meeting:
    meeting_id = str(uuid.uuid4())
    now = datetime.datetime.now(datetime.UTC)

    async with get_db() as db:
        await db.execute(
            """INSERT INTO meetings
               (id, title, started_at, primary_language, asr_live_engine,
                asr_post_engine, llm_provider, template_name,
                consent_recording, consent_voiceprint, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'recording')""",
            (
                meeting_id, title, now.isoformat(), language,
                asr_live_engine, asr_post_engine, llm_provider, template_name,
                consent_recording, consent_voiceprint,
            ),
        )
        await db.commit()

    await audit("CREATE", "meeting", meeting_id)
    logger.info("Meeting created", id=meeting_id, title=title)

    return Meeting(
        id=meeting_id,
        title=title,
        started_at=now,
        primary_language=language,
        asr_live_engine=asr_live_engine,
        asr_post_engine=asr_post_engine,
        llm_provider=llm_provider,
        template_name=template_name,
        consent_recording=consent_recording,
        consent_voiceprint=consent_voiceprint,
        status="recording",
    )


async def get_meeting(meeting_id: str) -> Optional[Meeting]:
    async with get_db() as db:
        cursor = await db.execute("SELECT * FROM meetings WHERE id = ?", (meeting_id,))
        row = await cursor.fetchone()
    if row is None:
        return None
    return _row_to_meeting(dict(row))


async def get_meeting_detail(meeting_id: str) -> Optional[MeetingDetail]:
    meeting = await get_meeting(meeting_id)
    if not meeting:
        return None

    summary = await get_latest_summary(meeting_id)
    actions = await list_action_items(meeting_id)
    count = await count_segments(meeting_id)

    return MeetingDetail(
        **meeting.model_dump(),
        summary=summary,
        action_items=actions,
        segment_count=count,
    )


async def list_meetings(
    page: int = 1,
    per_page: int = 20,
    language: Optional[str] = None,
    status: Optional[str] = None,
) -> list[Meeting]:
    offset = (page - 1) * per_page
    conditions = []
    params: list = []

    if language:
        conditions.append("primary_language = ?")
        params.append(language)
    if status:
        conditions.append("status = ?")
        params.append(status)

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    params += [per_page, offset]

    async with get_db() as db:
        cursor = await db.execute(
            f"SELECT * FROM meetings {where} ORDER BY started_at DESC LIMIT ? OFFSET ?",
            params,
        )
        rows = await cursor.fetchall()

    return [_row_to_meeting(dict(r)) for r in rows]


async def update_meeting(meeting_id: str, **kwargs) -> None:
    """Update meeting fields. Only provided kwargs are updated."""
    if not kwargs:
        return

    set_clauses = ", ".join(f"{k} = ?" for k in kwargs)
    values = list(kwargs.values()) + [meeting_id]

    async with get_db() as db:
        await db.execute(
            f"UPDATE meetings SET {set_clauses} WHERE id = ?", values
        )
        await db.commit()


async def delete_meeting(meeting_id: str) -> bool:
    """Full purge: cascade deletes all related data (Decree 356)."""
    async with get_db() as db:
        # Delete audio file if stored
        cursor = await db.execute(
            "SELECT audio_file_path FROM meetings WHERE id = ?", (meeting_id,)
        )
        row = await cursor.fetchone()
        if row and row["audio_file_path"]:
            import pathlib
            try:
                pathlib.Path(row["audio_file_path"]).unlink(missing_ok=True)
            except Exception:
                pass

        cursor = await db.execute("DELETE FROM meetings WHERE id = ?", (meeting_id,))
        await db.commit()
        deleted = cursor.rowcount > 0

    if deleted:
        await audit("PURGE", "meeting", meeting_id, "cascade delete all related data")
    return deleted


# ── Transcript Segments ───────────────────────────────────────────────────────

async def insert_segment(seg: TranscriptSegmentDB) -> int:
    async with get_db() as db:
        cursor = await db.execute(
            """INSERT INTO transcript_segments
               (meeting_id, speaker_label, speaker_name, text, start_time,
                end_time, confidence, language, source)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                seg.meeting_id, seg.speaker_label, seg.speaker_name, seg.text,
                seg.start_time, seg.end_time, seg.confidence,
                seg.language, seg.source,
            ),
        )
        await db.commit()
        return cursor.lastrowid


async def insert_segments_bulk(segments: list[TranscriptSegmentDB]) -> None:
    """Bulk insert transcript segments (efficient for POST processing)."""
    if not segments:
        return
    rows = [
        (
            s.meeting_id, s.speaker_label, s.speaker_name, s.text,
            s.start_time, s.end_time, s.confidence, s.language, s.source,
        )
        for s in segments
    ]
    async with get_db() as db:
        await db.executemany(
            """INSERT INTO transcript_segments
               (meeting_id, speaker_label, speaker_name, text, start_time,
                end_time, confidence, language, source)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            rows,
        )
        await db.commit()
    logger.info("Segments inserted", count=len(rows), meeting_id=segments[0].meeting_id)


async def get_transcript(meeting_id: str) -> list[TranscriptSegmentDB]:
    async with get_db() as db:
        cursor = await db.execute(
            """SELECT * FROM transcript_segments
               WHERE meeting_id = ?
               ORDER BY start_time ASC""",
            (meeting_id,),
        )
        rows = await cursor.fetchall()
    return [_row_to_segment(dict(r)) for r in rows]


async def count_segments(meeting_id: str) -> int:
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT COUNT(*) as cnt FROM transcript_segments WHERE meeting_id = ?",
            (meeting_id,),
        )
        row = await cursor.fetchone()
    return row["cnt"] if row else 0


async def delete_segments_by_source(meeting_id: str, source: str) -> None:
    """Delete LIVE segments before inserting POST segments."""
    async with get_db() as db:
        await db.execute(
            "DELETE FROM transcript_segments WHERE meeting_id = ? AND source = ?",
            (meeting_id, source),
        )
        await db.commit()


# ── Summaries ─────────────────────────────────────────────────────────────────

async def save_summary(
    meeting_id: str,
    content: str,
    template_name: Optional[str] = None,
    llm_provider: Optional[str] = None,
    llm_model: Optional[str] = None,
) -> Summary:
    async with get_db() as db:
        cursor = await db.execute(
            """INSERT INTO summaries
               (meeting_id, template_name, content, llm_provider, llm_model)
               VALUES (?, ?, ?, ?, ?)""",
            (meeting_id, template_name, content, llm_provider, llm_model),
        )
        await db.commit()
        summary_id = cursor.lastrowid

    await audit("CREATE", "summary", str(summary_id), f"meeting={meeting_id}")
    return Summary(
        id=summary_id,
        meeting_id=meeting_id,
        template_name=template_name,
        content=content,
        llm_provider=llm_provider,
        llm_model=llm_model,
    )


async def get_latest_summary(meeting_id: str) -> Optional[Summary]:
    async with get_db() as db:
        cursor = await db.execute(
            """SELECT * FROM summaries WHERE meeting_id = ?
               ORDER BY generated_at DESC LIMIT 1""",
            (meeting_id,),
        )
        row = await cursor.fetchone()
    if not row:
        return None
    return Summary(**dict(row))


# ── Action Items ──────────────────────────────────────────────────────────────

async def save_action_items(meeting_id: str, items: list[dict]) -> list[ActionItem]:
    """Save extracted action items from LLM output."""
    saved = []
    async with get_db() as db:
        for item in items:
            cursor = await db.execute(
                """INSERT INTO action_items
                   (meeting_id, description, owner, deadline, status)
                   VALUES (?, ?, ?, ?, 'open')""",
                (
                    meeting_id,
                    item.get("description", ""),
                    item.get("owner"),
                    item.get("deadline"),
                ),
            )
            saved.append(ActionItem(
                id=cursor.lastrowid,
                meeting_id=meeting_id,
                description=item.get("description", ""),
                owner=item.get("owner"),
                deadline=item.get("deadline"),
            ))
        await db.commit()
    return saved


async def list_action_items(meeting_id: str) -> list[ActionItem]:
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT * FROM action_items WHERE meeting_id = ? ORDER BY id ASC",
            (meeting_id,),
        )
        rows = await cursor.fetchall()
    return [ActionItem(**dict(r)) for r in rows]


async def update_action_item_status(item_id: int, status: str) -> None:
    async with get_db() as db:
        await db.execute(
            "UPDATE action_items SET status = ? WHERE id = ?",
            (status, item_id),
        )
        await db.commit()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _row_to_meeting(row: dict) -> Meeting:
    return Meeting(
        id=row["id"],
        title=row["title"],
        started_at=_parse_dt(row.get("started_at")),
        ended_at=_parse_dt(row.get("ended_at")),
        duration_seconds=row.get("duration_seconds"),
        audio_retained=bool(row.get("audio_retained", 0)),
        audio_file_path=row.get("audio_file_path"),
        primary_language=row.get("primary_language", "vi"),
        asr_live_engine=row.get("asr_live_engine"),
        asr_post_engine=row.get("asr_post_engine"),
        llm_provider=row.get("llm_provider"),
        template_name=row.get("template_name"),
        consent_recording=bool(row.get("consent_recording", 0)),
        consent_voiceprint=bool(row.get("consent_voiceprint", 0)),
        status=row.get("status", "recording"),
        created_at=_parse_dt(row.get("created_at")),
        updated_at=_parse_dt(row.get("updated_at")),
    )


def _row_to_segment(row: dict) -> TranscriptSegmentDB:
    return TranscriptSegmentDB(
        id=row.get("id"),
        meeting_id=row["meeting_id"],
        speaker_label=row.get("speaker_label"),
        speaker_name=row.get("speaker_name"),
        text=row["text"],
        start_time=row["start_time"],
        end_time=row["end_time"],
        confidence=row.get("confidence"),
        language=row.get("language"),
        source=row.get("source", "live"),
        created_at=_parse_dt(row.get("created_at")),
    )


def _parse_dt(value) -> Optional[datetime.datetime]:
    if value is None:
        return None
    if isinstance(value, datetime.datetime):
        return value
    try:
        return datetime.datetime.fromisoformat(str(value))
    except Exception:
        return None
