"""Comprehensive tests for storage repository CRUD operations.

Tests all database operations for meetings, segments, summaries, and action items.
Run: pytest tests/backend/test_storage_repository.py -v
"""

import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path

# Test configuration to use temp database
@pytest.fixture(autouse=True)
def temp_db(tmp_path):
    """Use a temporary SQLite database for each test."""
    from unittest.mock import MagicMock

    mock = MagicMock()
    mock.database_path = tmp_path / "test_meetscribe.db"
    mock.data_dir = tmp_path
    mock.db_key = "testkey123456789012345678901234"

    with patch("backend.config.settings", mock):
        with patch("backend.database.settings", mock):
            yield mock


@pytest.mark.asyncio
async def test_init_db_creates_all_tables():
    """Test that init_db creates all required tables."""
    from backend.database import init_db

    await init_db()

    from backend.database import get_db
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
        tables = {row["name"] for row in await cursor.fetchall()}

    expected = {
        "meetings", "transcript_segments", "summaries",
        "action_items", "speaker_voiceprints", "meeting_hotwords",
        "segment_embeddings", "config", "audit_log",
    }
    assert expected.issubset(tables), f"Missing tables: {expected - tables}"


@pytest.mark.asyncio
async def test_create_meeting_basic():
    """Test creating a basic meeting."""
    from backend.database import init_db
    from backend.storage.repository import create_meeting, get_meeting

    await init_db()

    meeting = await create_meeting(
        title="Test Meeting",
        language="vi",
        consent_recording=True,
        consent_voiceprint=False,
    )

    assert meeting.id is not None
    assert meeting.title == "Test Meeting"
    assert meeting.primary_language == "vi"
    assert meeting.status == "recording"
    assert meeting.consent_recording is True
    assert meeting.consent_voiceprint is False


@pytest.mark.asyncio
async def test_create_meeting_all_fields():
    """Test creating a meeting with all fields."""
    from backend.database import init_db
    from backend.storage.repository import create_meeting

    await init_db()  # Ensure tables exist

    meeting = await create_meeting(
        title="Full Meeting",
        language="en",
        asr_live_engine="faster-whisper",
        asr_post_engine="vibevoice",
        llm_provider="ollama",
        template_name="general",
        consent_recording=True,
        consent_voiceprint=True,
    )

    assert meeting.asr_live_engine == "faster-whisper"
    assert meeting.asr_post_engine == "vibevoice"
    assert meeting.llm_provider == "ollama"
    assert meeting.template_name == "general"


@pytest.mark.asyncio
async def test_get_meeting_not_found():
    """Test getting a non-existent meeting returns None."""
    from backend.database import init_db
    from backend.storage.repository import get_meeting

    await init_db()

    result = await get_meeting("nonexistent-id")
    assert result is None


@pytest.mark.asyncio
async def test_update_meeting():
    """Test updating meeting fields."""
    from backend.database import init_db
    from backend.storage.repository import create_meeting, get_meeting, update_meeting

    await init_db()

    meeting = await create_meeting(title="Original Title", language="vi")

    await update_meeting(meeting.id, title="Updated Title", status="complete")

    updated = await get_meeting(meeting.id)
    assert updated.title == "Updated Title"
    assert updated.status == "complete"


@pytest.mark.asyncio
async def test_update_meeting_partial():
    """Test partial update doesn't overwrite other fields."""
    from backend.database import init_db
    from backend.storage.repository import create_meeting, get_meeting, update_meeting

    await init_db()

    meeting = await create_meeting(title="Test", language="vi")
    original_id = meeting.id

    await update_meeting(meeting.id, status="complete")

    fetched = await get_meeting(original_id)
    assert fetched.title == "Test"  # Title unchanged
    assert fetched.status == "complete"


@pytest.mark.asyncio
async def test_list_meetings_pagination():
    """Test listing meetings with pagination."""
    from backend.database import init_db
    from backend.storage.repository import create_meeting, list_meetings

    await init_db()

    # Create 25 meetings
    for i in range(25):
        await create_meeting(title=f"Meeting {i}", language="vi")

    # Get first page
    page1 = await list_meetings(page=1, per_page=10)
    assert len(page1) == 10

    # Get second page
    page2 = await list_meetings(page=2, per_page=10)
    assert len(page2) == 10

    # Get third page
    page3 = await list_meetings(page=3, per_page=10)
    assert len(page3) == 5


@pytest.mark.asyncio
async def test_list_meetings_filter_by_language():
    """Test filtering meetings by language."""
    from backend.database import init_db
    from backend.storage.repository import create_meeting, list_meetings

    await init_db()

    await create_meeting(title="VI Meeting", language="vi")
    await create_meeting(title="EN Meeting", language="en")
    await create_meeting(title="Another VI", language="vi")

    vi_meetings = await list_meetings(language="vi")
    assert len(vi_meetings) == 2

    en_meetings = await list_meetings(language="en")
    assert len(en_meetings) == 1


@pytest.mark.asyncio
async def test_list_meetings_filter_by_status():
    """Test filtering meetings by status."""
    from backend.database import init_db
    from backend.storage.repository import create_meeting, list_meetings, update_meeting

    await init_db()

    m1 = await create_meeting(title="Recording", language="vi")
    m2 = await create_meeting(title="Complete", language="vi")
    m3 = await create_meeting(title="Error", language="vi")

    await update_meeting(m2.id, status="complete")

    recording = await list_meetings(status="recording")
    assert len(recording) == 2

    complete = await list_meetings(status="complete")
    assert len(complete) == 1


@pytest.mark.asyncio
async def test_insert_segment():
    """Test inserting a single transcript segment."""
    from backend.database import init_db
    from backend.storage.repository import create_meeting, insert_segment, get_transcript
    from backend.storage.models import TranscriptSegmentDB

    await init_db()

    meeting = await create_meeting(title="Seg Test", language="vi")

    seg = TranscriptSegmentDB(
        meeting_id=meeting.id,
        text="Xin chào các bạn",
        start_time=0.5,
        end_time=2.3,
        confidence=0.95,
        language="vi",
        speaker_label="SPEAKER_00",
        source="live",
    )

    seg_id = await insert_segment(seg)
    assert seg_id > 0

    segments = await get_transcript(meeting.id)
    assert len(segments) == 1
    assert segments[0].text == "Xin chào các bạn"
    assert segments[0].speaker_label == "SPEAKER_00"


@pytest.mark.asyncio
async def test_insert_multiple_segments():
    """Test inserting multiple segments maintains order."""
    from backend.database import init_db
    from backend.storage.repository import create_meeting, insert_segment, get_transcript
    from backend.storage.models import TranscriptSegmentDB

    await init_db()

    meeting = await create_meeting(title="Multi Seg", language="vi")

    for i in range(5):
        seg = TranscriptSegmentDB(
            meeting_id=meeting.id,
            text=f"Segment {i}",
            start_time=i * 1.0,
            end_time=(i + 1) * 1.0,
            confidence=0.9,
            language="vi",
            speaker_label=f"SPEAKER_{i % 2}",
            source="live",
        )
        await insert_segment(seg)

    segments = await get_transcript(meeting.id)
    assert len(segments) == 5
    assert segments[0].text == "Segment 0"
    assert segments[4].text == "Segment 4"


@pytest.mark.asyncio
async def test_insert_segments_bulk():
    """Test bulk insert of segments."""
    from backend.database import init_db
    from backend.storage.repository import create_meeting, insert_segments_bulk, get_transcript
    from backend.storage.models import TranscriptSegmentDB

    await init_db()

    meeting = await create_meeting(title="Bulk Test", language="vi")

    segments = [
        TranscriptSegmentDB(
            meeting_id=meeting.id,
            text=f"Bulk segment {i}",
            start_time=i * 0.5,
            end_time=(i + 1) * 0.5,
            confidence=0.85,
            language="vi",
            speaker_label="SPEAKER_00",
            source="post",
        )
        for i in range(10)
    ]

    await insert_segments_bulk(segments)

    retrieved = await get_transcript(meeting.id)
    assert len(retrieved) == 10


@pytest.mark.asyncio
async def test_delete_segments_by_source():
    """Test deleting segments by source type."""
    from backend.database import init_db
    from backend.storage.repository import (
        create_meeting, insert_segments_bulk, get_transcript,
        delete_segments_by_source,
    )
    from backend.storage.models import TranscriptSegmentDB

    await init_db()

    meeting = await create_meeting(title="Source Test", language="vi")

    # Insert both LIVE and POST segments
    segments = []
    for i in range(5):
        segments.append(TranscriptSegmentDB(
            meeting_id=meeting.id,
            text=f"Live {i}",
            start_time=i,
            end_time=i + 1,
            confidence=0.9,
            language="vi",
            speaker_label="SPEAKER_00",
            source="live",
        ))
        segments.append(TranscriptSegmentDB(
            meeting_id=meeting.id,
            text=f"Post {i}",
            start_time=i,
            end_time=i + 1,
            confidence=0.9,
            language="vi",
            speaker_label="SPEAKER_00",
            source="post",
        ))

    await insert_segments_bulk(segments)

    # Verify both sources exist
    all_segs = await get_transcript(meeting.id)
    assert len(all_segs) == 10

    # Delete only LIVE segments
    await delete_segments_by_source(meeting.id, "live")

    remaining = await get_transcript(meeting.id)
    assert len(remaining) == 5
    for seg in remaining:
        assert seg.source == "post"


@pytest.mark.asyncio
async def test_save_and_get_summary():
    """Test saving and retrieving a summary."""
    from backend.database import init_db
    from backend.storage.repository import create_meeting, save_summary, get_latest_summary

    await init_db()

    meeting = await create_meeting(title="Summary Test", language="vi")

    summary_content = "## Tóm tắt\n\nCuộc họp đã diễn ra tốt đẹp."

    summary = await save_summary(
        meeting_id=meeting.id,
        content=summary_content,
        template_name="general_vi",
        llm_provider="ollama",
        llm_model="qwen3:8b",
    )

    assert summary.meeting_id == meeting.id
    assert summary.content == summary_content

    retrieved = await get_latest_summary(meeting.id)
    assert retrieved is not None
    assert retrieved.content == summary_content


@pytest.mark.asyncio
async def test_save_action_items():
    """Test saving action items."""
    from backend.database import init_db
    from backend.storage.repository import create_meeting, save_action_items, list_action_items

    await init_db()

    meeting = await create_meeting(title="Action Items Test", language="vi")

    items = [
        {"description": "Complete the report", "owner": "Alice", "deadline": "2026-04-15"},
        {"description": "Review pull requests", "owner": "Bob", "deadline": "2026-04-16"},
    ]

    saved = await save_action_items(meeting.id, items)

    assert len(saved) == 2
    assert saved[0].description == "Complete the report"
    assert saved[0].owner == "Alice"
    assert saved[1].description == "Review pull requests"

    # Verify via list
    listed = await list_action_items(meeting.id)
    assert len(listed) == 2


@pytest.mark.asyncio
async def test_count_segments():
    """Test segment counting."""
    from backend.database import init_db
    from backend.storage.repository import create_meeting, insert_segment, count_segments
    from backend.storage.models import TranscriptSegmentDB

    await init_db()

    meeting = await create_meeting(title="Count Test", language="vi")

    assert await count_segments(meeting.id) == 0

    for i in range(5):
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

    assert await count_segments(meeting.id) == 5


@pytest.mark.asyncio
async def test_delete_meeting_cascade():
    """Test that deleting a meeting cascades to segments."""
    from backend.database import init_db
    from backend.storage.repository import (
        create_meeting, insert_segment, get_transcript,
        delete_meeting, count_segments,
    )
    from backend.storage.models import TranscriptSegmentDB

    await init_db()

    meeting = await create_meeting(title="Cascade Test", language="vi")

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

    assert await count_segments(meeting.id) == 3

    deleted = await delete_meeting(meeting.id)
    assert deleted is True

    # Segments should be gone
    assert await count_segments(meeting.id) == 0


@pytest.mark.asyncio
async def test_get_meeting_detail():
    """Test getting meeting detail with summary and action items."""
    from backend.database import init_db
    from backend.storage.repository import (
        create_meeting, save_summary, save_action_items,
        get_meeting_detail,
    )

    await init_db()

    meeting = await create_meeting(title="Detail Test", language="vi")

    await save_summary(
        meeting_id=meeting.id,
        content="Test summary",
        template_name="general_vi",
        llm_provider="ollama",
    )

    await save_action_items(meeting.id, [
        {"description": "Task 1", "owner": "Alice"},
    ])

    detail = await get_meeting_detail(meeting.id)

    assert detail.id == meeting.id
    assert detail.title == "Detail Test"
    assert detail.summary is not None
    assert detail.summary.content == "Test summary"
    assert len(detail.action_items) == 1
    assert detail.segment_count == 0  # No segments in this test


class TestAuditLog:
    """Tests for audit logging."""

    @pytest.mark.asyncio
    async def test_audit_log_writes_entry(self):
        """Test that audit() writes to audit_log table."""
        from backend.database import init_db, get_db, audit

        await init_db()

        await audit("CREATE", "meeting", "test-meeting-123", '{"title": "Test"}')

        async with get_db() as db:
            cursor = await db.execute(
                "SELECT * FROM audit_log WHERE entity_id = ?",
                ("test-meeting-123",)
            )
            row = await cursor.fetchone()

        assert row is not None
        assert row["action"] == "CREATE"
        assert row["entity_type"] == "meeting"
        assert row["entity_id"] == "test-meeting-123"
        assert row["details"] == '{"title": "Test"}'

    @pytest.mark.asyncio
    async def test_audit_log_multiple_entries(self):
        """Test multiple audit entries."""
        from backend.database import init_db, get_db, audit

        await init_db()

        await audit("CREATE", "meeting", "meeting-1")
        await audit("UPDATE", "meeting", "meeting-1")
        await audit("CREATE", "segment", "seg-1")

        async with get_db() as db:
            cursor = await db.execute("SELECT COUNT(*) as cnt FROM audit_log")
            count = (await cursor.fetchone())["cnt"]

        assert count == 3


class TestRepositoryHelpers:
    """Tests for repository helper functions."""

    def test_row_to_meeting_parsing(self):
        """Test _row_to_meeting correctly parses database rows."""
        from backend.storage.repository import _row_to_meeting
        import datetime

        row = {
            "id": "test-id",
            "title": "Test Meeting",
            "started_at": "2026-04-13T10:00:00+00:00",
            "ended_at": "2026-04-13T11:00:00+00:00",
            "duration_seconds": 3600,
            "audio_retained": 1,
            "audio_file_path": "/path/to/audio.wav",
            "primary_language": "vi",
            "asr_live_engine": "parakeet-vi",
            "asr_post_engine": "vibevoice",
            "llm_provider": "ollama",
            "template_name": "general_vi",
            "consent_recording": 1,
            "consent_voiceprint": 0,
            "status": "complete",
            "created_at": "2026-04-13T09:00:00+00:00",
            "updated_at": "2026-04-13T11:00:00+00:00",
        }

        meeting = _row_to_meeting(row)

        assert meeting.id == "test-id"
        assert meeting.title == "Test Meeting"
        assert meeting.duration_seconds == 3600
        assert meeting.audio_retained is True
        assert meeting.consent_voiceprint is False

    def test_row_to_segment_parsing(self):
        """Test _row_to_segment correctly parses database rows."""
        from backend.storage.repository import _row_to_segment

        row = {
            "id": 1,
            "meeting_id": "meeting-123",
            "speaker_label": "SPEAKER_00",
            "speaker_name": "Nguyễn Văn A",
            "text": "Xin chào",
            "start_time": 0.5,
            "end_time": 2.0,
            "confidence": 0.95,
            "language": "vi",
            "source": "live",
            "created_at": "2026-04-13T10:00:00+00:00",
        }

        seg = _row_to_segment(row)

        assert seg.id == 1
        assert seg.meeting_id == "meeting-123"
        assert seg.text == "Xin chào"
        assert seg.speaker_label == "SPEAKER_00"
        assert seg.speaker_name == "Nguyễn Văn A"