"""Tests for storage repository CRUD operations."""

import pytest
from unittest.mock import patch


@pytest.fixture(autouse=True)
def temp_db(tmp_path):
    from unittest.mock import MagicMock
    import pathlib
    mock = MagicMock()
    mock.database_path = tmp_path / "test.db"
    mock.data_dir = tmp_path
    mock.db_key = "testkey"
    with patch("backend.config.settings", mock):
        with patch("backend.database.settings", mock):
            yield mock


@pytest.mark.asyncio
async def test_create_and_get_meeting():
    from backend.database import init_db
    from backend.storage.repository import create_meeting, get_meeting

    await init_db()

    meeting = await create_meeting(
        title="Test Meeting",
        language="vi",
        consent_recording=True,
        consent_voiceprint=False,
    )

    assert meeting.id
    assert meeting.title == "Test Meeting"
    assert meeting.primary_language == "vi"
    assert meeting.consent_recording is True

    fetched = await get_meeting(meeting.id)
    assert fetched is not None
    assert fetched.id == meeting.id
    assert fetched.title == "Test Meeting"


@pytest.mark.asyncio
async def test_insert_and_get_segments():
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
