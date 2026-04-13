"""Data Subject Rights — full purge per Vietnam Decree 356/2025.

DELETE /api/meetings/{id}/purge cascades to:
  transcript_segments, summaries, action_items, meeting_hotwords,
  segment_embeddings, audio file on disk.

DELETE /api/compliance/voiceprints/{id} purges embedding only,
  without affecting transcripts.

All purge operations are logged in audit_log.

File: backend/compliance/data_purge.py
"""

from __future__ import annotations

import pathlib
from typing import Optional

import structlog

from backend.database import get_db, audit

logger = structlog.get_logger(__name__)


async def purge_meeting(meeting_id: str) -> dict:
    """Full purge of all data associated with a meeting.

    Cascade delete order (FK constraints satisfied by SQLite cascade):
      1. segment_embeddings (via transcript_segments cascade)
      2. transcript_segments
      3. summaries
      4. action_items
      5. meeting_hotwords
      6. meetings (parent — deleted last)
      7. Audio file on disk (if audio_retained=True)

    Returns summary of what was deleted.
    """
    deleted: dict[str, int | bool] = {}

    async with get_db() as db:
        # Capture audio path before deletion
        cursor = await db.execute(
            "SELECT audio_file_path, audio_retained FROM meetings WHERE id = ?",
            (meeting_id,),
        )
        row = await cursor.fetchone()
        if not row:
            return {"error": "Meeting not found"}

        audio_path = row["audio_file_path"]
        audio_retained = bool(row["audio_retained"])

        # Count what will be deleted
        for table in ("transcript_segments", "summaries", "action_items", "meeting_hotwords"):
            cur = await db.execute(
                f"SELECT COUNT(*) as cnt FROM {table} WHERE meeting_id = ?",
                (meeting_id,),
            )
            r = await cur.fetchone()
            deleted[table] = r["cnt"] if r else 0

        # Cascade delete (SQLite handles child tables via ON DELETE CASCADE)
        await db.execute("DELETE FROM meetings WHERE id = ?", (meeting_id,))
        await db.commit()
        deleted["meetings"] = 1

    # Delete audio file from disk
    deleted["audio_file"] = False
    if audio_retained and audio_path:
        try:
            pathlib.Path(audio_path).unlink(missing_ok=True)
            deleted["audio_file"] = True
            logger.info("Audio file purged", path=audio_path)
        except Exception as exc:
            logger.error("Failed to delete audio file", path=audio_path, error=str(exc))

    await audit(
        "PURGE",
        "meeting",
        meeting_id,
        f"deleted={deleted}",
    )
    logger.info("Meeting purged", meeting_id=meeting_id, summary=deleted)
    return deleted


async def purge_voiceprint(voiceprint_id: str) -> bool:
    """Delete a single voiceprint embedding (Decree 356 data subject right).

    Does NOT affect transcripts — speaker labels remain but lose the
    voice identity association.
    """
    async with get_db() as db:
        cursor = await db.execute(
            "DELETE FROM speaker_voiceprints WHERE id = ?", (voiceprint_id,)
        )
        await db.commit()
        deleted = cursor.rowcount > 0

    if deleted:
        await audit("DELETE", "voiceprint", voiceprint_id)
        logger.info("Voiceprint purged", id=voiceprint_id)

    return deleted


async def purge_all_voiceprints() -> int:
    """Delete ALL stored voiceprints (nuclear option for privacy compliance)."""
    async with get_db() as db:
        cursor = await db.execute("DELETE FROM speaker_voiceprints")
        await db.commit()
        count = cursor.rowcount

    await audit("PURGE_ALL", "voiceprint", "all", f"count={count}")
    logger.warning("All voiceprints purged", count=count)
    return count
