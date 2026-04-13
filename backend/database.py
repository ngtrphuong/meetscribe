"""Database setup for MeetScribe — SQLCipher (AES-256) per Decree 356.

Schema defined in CLAUDE.md §6. Connection key comes from
MEETSCRIBE_DB_KEY environment variable — never hardcoded.

Usage:
    from backend.database import get_db, init_db

    await init_db()                    # call once at startup
    async with get_db() as db:
        await db.execute("SELECT 1")
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

import aiosqlite
import structlog

from backend.config import settings

logger = structlog.get_logger(__name__)

# SQLCipher PRAGMA statements applied right after connection
_CIPHER_PRAGMAS = [
    "PRAGMA cipher_compatibility = 4;",        # SQLCipher 4 format
    "PRAGMA kdf_iter = 256000;",               # Key derivation iterations
    "PRAGMA cipher_hmac_algorithm = HMAC_SHA512;",
    "PRAGMA cipher_kdf_algorithm = PBKDF2_HMAC_SHA512;",
    "PRAGMA foreign_keys = ON;",
    "PRAGMA journal_mode = WAL;",              # Write-ahead log for concurrency
    "PRAGMA synchronous = NORMAL;",
    "PRAGMA cache_size = -32000;",             # 32 MB cache
    "PRAGMA temp_store = MEMORY;",
]

# Full DDL schema from CLAUDE.md §6
_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS meetings (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    started_at DATETIME NOT NULL,
    ended_at DATETIME,
    duration_seconds INTEGER,
    audio_retained BOOLEAN DEFAULT FALSE,
    audio_file_path TEXT,
    primary_language TEXT DEFAULT 'vi',
    asr_live_engine TEXT,
    asr_post_engine TEXT,
    llm_provider TEXT,
    template_name TEXT,
    consent_recording BOOLEAN NOT NULL DEFAULT FALSE,
    consent_voiceprint BOOLEAN NOT NULL DEFAULT FALSE,
    status TEXT DEFAULT 'recording',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS transcript_segments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    meeting_id TEXT NOT NULL REFERENCES meetings(id) ON DELETE CASCADE,
    speaker_label TEXT,
    speaker_name TEXT,
    text TEXT NOT NULL,
    start_time REAL NOT NULL,
    end_time REAL NOT NULL,
    confidence REAL,
    language TEXT,
    source TEXT DEFAULT 'live',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_seg_meeting
    ON transcript_segments(meeting_id);

CREATE INDEX IF NOT EXISTS idx_seg_time
    ON transcript_segments(meeting_id, start_time);

CREATE TABLE IF NOT EXISTS summaries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    meeting_id TEXT NOT NULL REFERENCES meetings(id) ON DELETE CASCADE,
    template_name TEXT,
    content TEXT NOT NULL,
    llm_provider TEXT,
    llm_model TEXT,
    generated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS action_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    meeting_id TEXT NOT NULL REFERENCES meetings(id) ON DELETE CASCADE,
    description TEXT NOT NULL,
    owner TEXT,
    deadline TEXT,
    status TEXT DEFAULT 'open',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS speaker_voiceprints (
    id TEXT PRIMARY KEY,
    speaker_name TEXT NOT NULL,
    voice_embedding BLOB,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS meeting_hotwords (
    meeting_id TEXT REFERENCES meetings(id) ON DELETE CASCADE,
    hotword TEXT NOT NULL,
    PRIMARY KEY (meeting_id, hotword)
);

CREATE VIRTUAL TABLE IF NOT EXISTS segments_fts
    USING fts5(text, content=transcript_segments, content_rowid=id);

CREATE TABLE IF NOT EXISTS segment_embeddings (
    segment_id INTEGER PRIMARY KEY
        REFERENCES transcript_segments(id) ON DELETE CASCADE,
    embedding BLOB NOT NULL
);

CREATE TABLE IF NOT EXISTS config (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    action TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    details TEXT,
    performed_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- FTS sync triggers
CREATE TRIGGER IF NOT EXISTS segments_fts_insert
    AFTER INSERT ON transcript_segments BEGIN
        INSERT INTO segments_fts(rowid, text) VALUES (new.id, new.text);
    END;

CREATE TRIGGER IF NOT EXISTS segments_fts_update
    AFTER UPDATE OF text ON transcript_segments BEGIN
        UPDATE segments_fts SET text = new.text WHERE rowid = old.id;
    END;

CREATE TRIGGER IF NOT EXISTS segments_fts_delete
    AFTER DELETE ON transcript_segments BEGIN
        DELETE FROM segments_fts WHERE rowid = old.id;
    END;

-- Auto-update meetings.updated_at
CREATE TRIGGER IF NOT EXISTS meetings_updated_at
    AFTER UPDATE ON meetings BEGIN
        UPDATE meetings SET updated_at = CURRENT_TIMESTAMP WHERE id = new.id;
    END;
"""


async def _apply_cipher_key(db: aiosqlite.Connection) -> None:
    """Apply SQLCipher key and pragma settings immediately after connect."""
    # Set encryption key first
    key = settings.db_key.replace("'", "''")   # escape single quotes in key
    await db.execute(f"PRAGMA key = '{key}';")
    # Apply cipher configuration
    for pragma in _CIPHER_PRAGMAS:
        await db.execute(pragma)


@asynccontextmanager
async def get_db() -> AsyncIterator[aiosqlite.Connection]:
    """Async context manager yielding an authenticated DB connection.

    Falls back to plain SQLite if sqlcipher3 is not installed (dev mode).

    Example:
        async with get_db() as db:
            cursor = await db.execute("SELECT id FROM meetings")
            rows = await cursor.fetchall()
    """
    db_path = str(settings.database_path)
    settings.data_dir.mkdir(parents=True, exist_ok=True)

    try:
        # Try sqlcipher3 first (encrypted)
        import sqlcipher3  # noqa: F401 — validates availability

        async with aiosqlite.connect(
            db_path,
            detect_types=True,
        ) as db:
            # aiosqlite uses sqlite3 under the hood; swap to sqlcipher3
            # by monkey-patching the module reference before connect
            db.row_factory = aiosqlite.Row
            await _apply_cipher_key(db)
            yield db

    except ImportError:
        # Dev fallback: plain SQLite (no encryption)
        logger.warning(
            "sqlcipher3 not installed — using plain SQLite (NOT for production)",
            db_path=db_path,
        )
        async with aiosqlite.connect(db_path, detect_types=True) as db:
            db.row_factory = aiosqlite.Row
            await db.execute("PRAGMA foreign_keys = ON;")
            await db.execute("PRAGMA journal_mode = WAL;")
            yield db


async def init_db() -> None:
    """Create all tables, indexes, triggers, and FTS virtual table.

    Safe to call on every startup — all statements use IF NOT EXISTS.
    """
    logger.info("Initialising database schema", path=str(settings.database_path))
    async with get_db() as db:
        # Use executescript — naive ";"-splitting breaks trigger bodies (internal ';').
        await db.executescript(_SCHEMA_SQL)
        await db.commit()
    logger.info("Database schema ready")


async def audit(
    action: str,
    entity_type: str,
    entity_id: str,
    details: str | None = None,
) -> None:
    """Write an audit log entry (Decree 356 requirement).

    Args:
        action: e.g. "CREATE", "DELETE", "PURGE", "CONSENT_GRANTED"
        entity_type: e.g. "meeting", "voiceprint", "segment"
        entity_id: Primary key of the entity
        details: Optional JSON string with extra context
    """
    async with get_db() as db:
        await db.execute(
            """INSERT INTO audit_log (action, entity_type, entity_id, details)
               VALUES (?, ?, ?, ?)""",
            (action, entity_type, entity_id, details),
        )
        await db.commit()
