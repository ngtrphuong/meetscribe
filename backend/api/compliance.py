"""Compliance API — Consent, Purge, Voiceprints, Audit Log (Decree 356).

GET    /api/compliance/consent/{meeting_id}
POST   /api/compliance/consent
DELETE /api/compliance/voiceprints/{speaker_id}
DELETE /api/compliance/voiceprints
GET    /api/compliance/audit-log

File: backend/api/compliance.py
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

router = APIRouter()


class ConsentRequest(BaseModel):
    meeting_id: str
    consent_recording: bool = False
    consent_voiceprint: bool = False


@router.get("/consent/{meeting_id}")
async def get_consent(meeting_id: str):
    """Get current consent state for a meeting."""
    from backend.compliance.consent import get_consent as db_get_consent
    result = await db_get_consent(meeting_id)
    if not result.get("found"):
        raise HTTPException(status_code=404, detail="Meeting not found")
    return result


@router.post("/consent")
async def record_consent(req: ConsentRequest):
    """Record consent decisions before recording begins.

    MUST be called before starting a recording session.
    """
    from backend.compliance.consent import record_consent as db_record
    await db_record(
        req.meeting_id,
        consent_recording=req.consent_recording,
        consent_voiceprint=req.consent_voiceprint,
    )
    return {
        "meeting_id": req.meeting_id,
        "consent_recording": req.consent_recording,
        "consent_voiceprint": req.consent_voiceprint,
        "recorded": True,
    }


@router.delete("/voiceprints/{speaker_id}")
async def delete_voiceprint(speaker_id: str):
    """Delete a specific speaker voiceprint (biometric data erasure)."""
    from backend.compliance.data_purge import purge_voiceprint
    deleted = await purge_voiceprint(speaker_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Voiceprint not found")
    return {"deleted": True, "id": speaker_id}


@router.delete("/voiceprints")
async def delete_all_voiceprints():
    """Delete ALL voiceprints (nuclear privacy option)."""
    from backend.compliance.data_purge import purge_all_voiceprints
    count = await purge_all_voiceprints()
    return {"deleted_count": count}


@router.get("/audit-log")
async def get_audit_log(
    entity_type: Optional[str] = Query(None),
    entity_id: Optional[str] = Query(None),
    action: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    """Query the audit log for compliance reporting."""
    from backend.compliance.audit_log import get_audit_log as db_audit
    entries = await db_audit(
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        limit=limit,
        offset=offset,
    )
    return {"entries": [e.model_dump() for e in entries], "count": len(entries)}
