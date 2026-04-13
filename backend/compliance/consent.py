"""Consent management for Vietnam Decree 356/2025.

Two consent flags are required before any data capture:
  consent_recording  — permission to save audio file to disk
  consent_voiceprint — permission to extract speaker voice embeddings

These are stored per-meeting in the meetings table and checked by
the orchestrator before enabling corresponding features.

File: backend/compliance/consent.py
"""

from __future__ import annotations

from backend.database import get_db, audit


async def record_consent(
    meeting_id: str,
    consent_recording: bool,
    consent_voiceprint: bool,
) -> None:
    """Update consent flags for a meeting and write audit log entry."""
    async with get_db() as db:
        await db.execute(
            """UPDATE meetings
               SET consent_recording = ?, consent_voiceprint = ?
               WHERE id = ?""",
            (consent_recording, consent_voiceprint, meeting_id),
        )
        await db.commit()

    await audit(
        "CONSENT_GRANTED",
        "meeting",
        meeting_id,
        f"recording={consent_recording} voiceprint={consent_voiceprint}",
    )


async def get_consent(meeting_id: str) -> dict:
    """Return current consent state for a meeting."""
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT consent_recording, consent_voiceprint FROM meetings WHERE id = ?",
            (meeting_id,),
        )
        row = await cursor.fetchone()

    if not row:
        return {"meeting_id": meeting_id, "found": False}

    return {
        "meeting_id": meeting_id,
        "found": True,
        "consent_recording": bool(row["consent_recording"]),
        "consent_voiceprint": bool(row["consent_voiceprint"]),
    }
