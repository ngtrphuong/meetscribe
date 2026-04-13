"""Tests for database initialization and basic CRUD operations.

Uses in-memory SQLite (plain, no SQLCipher) for fast testing.
Run: pytest tests/backend/test_database.py -v
"""

import pytest
from unittest.mock import MagicMock, patch

# Override settings to use a temp DB file
@pytest.fixture(autouse=True)
def temp_db(tmp_path):
    """Use a temporary SQLite database for each test."""
    db_path = tmp_path / "test_meetscribe.db"
    mock_settings = MagicMock()
    mock_settings.database_path = db_path
    mock_settings.data_dir = tmp_path
    mock_settings.db_key = "test_key"
    # database.py holds a reference to settings at import time — patch both
    with patch("backend.config.settings", mock_settings):
        with patch("backend.database.settings", mock_settings):
            yield mock_settings


@pytest.mark.asyncio
async def test_init_db_creates_tables():
    """Database initialization creates all required tables."""
    from backend.database import init_db, get_db

    await init_db()

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
async def test_audit_log():
    """audit() writes entries to audit_log table."""
    from backend.database import init_db, get_db, audit

    await init_db()
    await audit("CREATE", "meeting", "test-id-123", '{"title": "Test"}')

    async with get_db() as db:
        cursor = await db.execute(
            "SELECT * FROM audit_log WHERE entity_id = ?", ("test-id-123",)
        )
        row = await cursor.fetchone()

    assert row is not None
    assert row["action"] == "CREATE"
    assert row["entity_type"] == "meeting"
    assert row["entity_id"] == "test-id-123"
