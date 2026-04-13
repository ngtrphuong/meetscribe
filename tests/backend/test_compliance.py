"""Comprehensive tests for compliance modules.

Tests consent management, audit log queries, and data purge operations
for Vietnam Decree 356/2025 compliance.
Run: pytest tests/backend/test_compliance.py -v
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from pathlib import Path

# Test configuration — use temp database
@pytest.fixture(autouse=True)
def temp_db(tmp_path):
    """Use a temporary SQLite database for each test."""
    mock = MagicMock()
    mock.database_path = tmp_path / "test_compliance.db"
    mock.data_dir = tmp_path
    mock.db_key = "testkey123456789012345678901234"

    with patch("backend.config.settings", mock):
        with patch("backend.database.settings", mock):
            yield mock


@pytest.mark.asyncio
async def test_record_consent_updates_flags():
    """Test record_consent() updates both flags in DB."""
    from backend.database import init_db
    from backend.compliance.consent import record_consent
    from backend.storage.repository import create_meeting

    await init_db()

    meeting = await create_meeting(title="Consent Test", language="vi")

    await record_consent(
        meeting_id=meeting.id,
        consent_recording=True,
        consent_voiceprint=False,
    )

    from backend.compliance.consent import get_consent
    result = await get_consent(meeting.id)

    assert result["found"] is True
    assert result["consent_recording"] is True
    assert result["consent_voiceprint"] is False


@pytest.mark.asyncio
async def test_record_consent_writes_audit_log():
    """Test record_consent() writes an audit log entry."""
    from backend.database import init_db
    from backend.compliance.consent import record_consent
    from backend.storage.repository import create_meeting

    await init_db()

    meeting = await create_meeting(title="Audit Consent Test", language="vi")

    await record_consent(
        meeting_id=meeting.id,
        consent_recording=True,
        consent_voiceprint=True,
    )

    from backend.database import get_db
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT action, details FROM audit_log WHERE entity_id = ?",
            (meeting.id,),
        )
        rows = await cursor.fetchall()

    assert len(rows) >= 1
    actions = {r["action"] for r in rows}
    assert "CONSENT_GRANTED" in actions


@pytest.mark.asyncio
async def test_get_consent_not_found():
    """Test get_consent() returns found=False for unknown meeting."""
    from backend.database import init_db
    from backend.compliance.consent import get_consent

    await init_db()
    result = await get_consent("nonexistent-meeting-id")

    assert result["found"] is False
    assert result["meeting_id"] == "nonexistent-meeting-id"


@pytest.mark.asyncio
async def test_get_consent_unknown_meeting_id():
    """Test get_consent() returns found=False for non-existent meeting."""
    from backend.database import init_db
    from backend.compliance.consent import get_consent

    await init_db()

    result = await get_consent("meeting-that-does-not-exist")
    assert result["found"] is False


# ── Audit Log Query Tests ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_audit_log_empty():
    """Test get_audit_log() returns empty list when no entries."""
    from backend.database import init_db
    from backend.compliance.audit_log import get_audit_log

    await init_db()

    entries = await get_audit_log()
    assert isinstance(entries, list)


@pytest.mark.asyncio
async def test_get_audit_log_with_entries():
    """Test get_audit_log() returns all audit entries."""
    from backend.database import init_db, audit
    from backend.compliance.audit_log import get_audit_log

    await init_db()

    await audit("CREATE", "meeting", "m1", '{"title": "M1"}')
    await audit("UPDATE", "meeting", "m2", '{"title": "M2"}')
    await audit("CREATE", "segment", "s1")

    entries = await get_audit_log()

    assert len(entries) >= 3


@pytest.mark.asyncio
async def test_get_audit_log_filter_by_entity_type():
    """Test get_audit_log() filters by entity_type."""
    from backend.database import init_db, audit
    from backend.compliance.audit_log import get_audit_log

    await init_db()

    await audit("CREATE", "meeting", "m1")
    await audit("DELETE", "voiceprint", "vp1")
    await audit("CREATE", "meeting", "m2")

    entries = await get_audit_log(entity_type="meeting")
    assert all(e.entity_type == "meeting" for e in entries)


@pytest.mark.asyncio
async def test_get_audit_log_filter_by_entity_id():
    """Test get_audit_log() filters by entity_id."""
    from backend.database import init_db, audit
    from backend.compliance.audit_log import get_audit_log

    await init_db()

    await audit("CREATE", "meeting", "target-meeting", '{"title": "Target"}')
    await audit("CREATE", "meeting", "other-meeting")

    entries = await get_audit_log(entity_id="target-meeting")
    assert all(e.entity_id == "target-meeting" for e in entries)
    assert len(entries) == 1


@pytest.mark.asyncio
async def test_get_audit_log_filter_by_action():
    """Test get_audit_log() filters by action."""
    from backend.database import init_db, audit
    from backend.compliance.audit_log import get_audit_log

    await init_db()

    await audit("CREATE", "meeting", "m1")
    await audit("UPDATE", "meeting", "m1")
    await audit("PURGE", "meeting", "m2")

    entries = await get_audit_log(action="PURGE")
    assert all(e.action == "PURGE" for e in entries)


@pytest.mark.asyncio
async def test_get_audit_log_limit_offset():
    """Test get_audit_log() respects limit and offset."""
    from backend.database import init_db, audit
    from backend.compliance.audit_log import get_audit_log

    await init_db()

    for i in range(10):
        await audit("CREATE", "meeting", f"m{i}", f'{{"i": {i}}}')

    entries_page1 = await get_audit_log(limit=3, offset=0)
    entries_page2 = await get_audit_log(limit=3, offset=3)

    assert len(entries_page1) == 3
    assert len(entries_page2) == 3
    assert entries_page1[0].entity_id != entries_page2[0].entity_id


# ── Data Purge Tests ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_purge_meeting_not_found():
    """Test purge_meeting() returns error dict for unknown meeting."""
    from backend.database import init_db
    from backend.compliance.data_purge import purge_meeting

    await init_db()
    result = await purge_meeting("nonexistent-meeting-id")

    assert "error" in result
    assert result["error"] == "Meeting not found"


@pytest.mark.asyncio
async def test_purge_meeting_deletes_all_data():
    """Test purge_meeting() deletes meeting + cascade data."""
    from backend.database import init_db
    from backend.compliance.data_purge import purge_meeting
    from backend.storage.repository import (
        create_meeting, insert_segment, save_summary,
        save_action_items, count_segments,
    )
    from backend.storage.models import TranscriptSegmentDB

    await init_db()

    meeting = await create_meeting(title="Purge Test", language="vi")

    for i in range(3):
        seg = TranscriptSegmentDB(
            meeting_id=meeting.id,
            text=f"Segment {i}",
            start_time=i,
            end_time=i + 1,
            confidence=0.9,
            language="vi",
            source="live",
        )
        await insert_segment(seg)

    await save_summary(meeting.id, content="Test summary", template_name="general_vi")
    await save_action_items(meeting.id, [{"description": "Task 1"}])

    assert await count_segments(meeting.id) == 3

    deleted = await purge_meeting(meeting.id)

    assert "error" not in deleted
    assert deleted["meetings"] == 1
    assert deleted["transcript_segments"] == 3
    assert deleted["summaries"] == 1
    assert deleted["action_items"] == 1


@pytest.mark.asyncio
async def test_purge_meeting_with_audio_file(tmp_path):
    """Test purge_meeting() deletes audio file when audio_retained=True."""
    from backend.database import init_db
    from backend.compliance.data_purge import purge_meeting
    from backend.storage.repository import create_meeting, update_meeting

    await init_db()

    # Create fake audio file
    audio_dir = tmp_path / "recordings"
    audio_dir.mkdir()
    audio_path = audio_dir / "meeting-audio.wav"
    audio_path.write_bytes(b"fake wav content")

    meeting = await create_meeting(title="Audio Purge Test", language="vi")
    await update_meeting(meeting.id, audio_retained=True, audio_file_path=str(audio_path))

    # Verify file exists
    assert audio_path.exists()

    deleted = await purge_meeting(meeting.id)

    assert deleted["audio_file"] is True
    assert not audio_path.exists()


@pytest.mark.asyncio
async def test_purge_meeting_without_audio_consent(tmp_path):
    """Test purge_meeting() does NOT delete file when audio_retained=False."""
    from backend.database import init_db
    from backend.compliance.data_purge import purge_meeting
    from backend.storage.repository import create_meeting

    await init_db()

    audio_dir = tmp_path / "recordings"
    audio_dir.mkdir()
    audio_path = audio_dir / "meeting-audio.wav"
    audio_path.write_bytes(b"fake wav content")

    meeting = await create_meeting(title="No Audio Retain Test", language="vi")
    # audio_retained defaults to False, audio_file_path left as None

    deleted = await purge_meeting(meeting.id)

    assert deleted["audio_file"] is False
    assert audio_path.exists()  # File should NOT be deleted


@pytest.mark.asyncio
async def test_purge_meeting_writes_audit_log():
    """Test purge_meeting() writes PURGE audit log entry."""
    from backend.database import init_db
    from backend.compliance.data_purge import purge_meeting
    from backend.storage.repository import create_meeting

    await init_db()

    meeting = await create_meeting(title="Audit Purge Test", language="vi")
    await purge_meeting(meeting.id)

    from backend.database import get_db
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT action, entity_id FROM audit_log WHERE entity_id = ?",
            (meeting.id,),
        )
        rows = await cursor.fetchall()

    actions = {r["action"] for r in rows}
    assert "PURGE" in actions


@pytest.mark.asyncio
async def test_purge_voiceprint_deletes_embedding():
    """Test purge_voiceprint() deletes voiceprint without affecting meetings."""
    from backend.database import init_db
    from backend.compliance.data_purge import purge_voiceprint
    from backend.storage.repository import create_meeting
    from backend.database import get_db

    await init_db()

    meeting = await create_meeting(title="Voiceprint Test", language="vi")

    # Insert a voiceprint directly
    async with get_db() as db:
        await db.execute(
            """INSERT INTO speaker_voiceprints (id, speaker_name, voice_embedding)
               VALUES (?, ?, ?)""",
            ("vp-test-123", "Nguyễn Văn A", b"fake_embedding_data"),
        )
        await db.commit()

    deleted = await purge_voiceprint("vp-test-123")
    assert deleted is True

    # Verify it's gone
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT * FROM speaker_voiceprints WHERE id = ?", ("vp-test-123",)
        )
        row = await cursor.fetchone()
    assert row is None


@pytest.mark.asyncio
async def test_purge_voiceprint_not_found():
    """Test purge_voiceprint() returns False when ID not found."""
    from backend.database import init_db
    from backend.compliance.data_purge import purge_voiceprint

    await init_db()
    deleted = await purge_voiceprint("nonexistent-voiceprint-id")
    assert deleted is False


@pytest.mark.asyncio
async def test_purge_all_voiceprints_deletes_all():
    """Test purge_all_voiceprints() deletes all voiceprints."""
    from backend.database import init_db
    from backend.compliance.data_purge import purge_all_voiceprints
    from backend.database import get_db

    await init_db()

    # Insert multiple voiceprints
    async with get_db() as db:
        await db.executemany(
            """INSERT INTO speaker_voiceprints (id, speaker_name, voice_embedding)
               VALUES (?, ?, ?)""",
            [
                ("vp1", "Speaker 1", b"embed1"),
                ("vp2", "Speaker 2", b"embed2"),
                ("vp3", "Speaker 3", b"embed3"),
            ],
        )
        await db.commit()

    count = await purge_all_voiceprints()
    assert count == 3

    async with get_db() as db:
        cursor = await db.execute("SELECT COUNT(*) as cnt FROM speaker_voiceprints")
        row = await cursor.fetchone()
    assert row["cnt"] == 0


@pytest.mark.asyncio
async def test_purge_all_voiceprints_writes_audit():
    """Test purge_all_voiceprints() writes audit log entry."""
    from backend.database import init_db
    from backend.compliance.data_purge import purge_all_voiceprints
    from backend.database import get_db

    await init_db()

    await purge_all_voiceprints()

    async with get_db() as db:
        cursor = await db.execute(
            "SELECT action, entity_id FROM audit_log WHERE action = 'PURGE_ALL'"
        )
        row = await cursor.fetchone()

    assert row is not None
    assert row["entity_id"] == "all"
