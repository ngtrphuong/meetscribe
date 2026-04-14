"""Comprehensive tests for FTS5 and semantic search.

Tests backend/storage/search.py — fts_search() and semantic_search().
Run: pytest tests/backend/test_search.py -v
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from pathlib import Path


# Use temp db for all tests
@pytest.fixture(autouse=True)
def temp_db(tmp_path):
    mock = MagicMock()
    mock.database_path = tmp_path / "test_compliance.db"
    mock.data_dir = tmp_path
    mock.db_key = "testkey123456789012345678901234"

    with patch("backend.config.settings", mock):
        with patch("backend.database.settings", mock):
            import backend.database as db_module
            db_module._settings_holder = None
            yield mock


@pytest.mark.asyncio
async def test_fts_search_returns_list():
    """fts_search() returns a list."""
    from backend.storage.search import fts_search

    with patch("backend.storage.search.get_db") as mock_get_db:
        mock_db = AsyncMock()
        mock_db.execute.return_value = MagicMock(fetchall=AsyncMock(return_value=[]))
        mock_db.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db.__aexit__ = AsyncMock(return_value=None)
        mock_get_db.return_value = mock_db

        result = await fts_search("test query")
        assert isinstance(result, list)


@pytest.mark.asyncio
async def test_fts_search_returns_matching_segments():
    """fts_search() returns segment dicts with required fields."""
    from backend.storage.search import fts_search

    mock_rows = [
        {
            "id": 1,
            "meeting_id": "m1",
            "speaker_label": "SPEAKER_00",
            "speaker_name": None,
            "text": "Xin chào thế giới",
            "start_time": 0.0,
            "end_time": 1.5,
            "language": "vi",
            "meeting_title": "Test Meeting",
            "started_at": "2026-04-13T10:00:00",
            "rank": -1.5,
        }
    ]

    with patch("backend.storage.search.get_db") as mock_get_db:
        mock_db = AsyncMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall = AsyncMock(return_value=mock_rows)
        mock_db.execute.return_value = mock_cursor
        mock_db.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db.__aexit__ = AsyncMock(return_value=None)
        mock_get_db.return_value = mock_db

        result = await fts_search("Xin chào")

        assert len(result) == 1
        assert result[0]["text"] == "Xin chào thế giới"
        assert result[0]["meeting_id"] == "m1"


@pytest.mark.asyncio
async def test_fts_search_with_language_filter():
    """fts_search() passes language filter to SQL."""
    from backend.storage.search import fts_search

    with patch("backend.storage.search.get_db") as mock_get_db:
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=MagicMock(fetchall=AsyncMock(return_value=[])))
        mock_db.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db.__aexit__ = AsyncMock(return_value=None)
        mock_get_db.return_value = mock_db

        await fts_search("test query", language="vi")

        # Check the SQL was called with language param
        call_args = mock_db.execute.call_args
        sql = call_args[0][0]
        params = call_args[0][1]
        assert "AND ts.language = ?" in sql
        assert "vi" in params


@pytest.mark.asyncio
async def test_fts_search_returns_empty_on_error():
    """fts_search() returns empty list when DB raises."""
    from backend.storage.search import fts_search

    with patch("backend.storage.search.get_db") as mock_get_db:
        mock_db = AsyncMock()
        mock_db.execute.side_effect = RuntimeError("DB error")
        mock_db.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db.__aexit__ = AsyncMock(return_value=None)
        mock_get_db.return_value = mock_db

        result = await fts_search("test query")
        assert result == []


@pytest.mark.asyncio
async def test_semantic_search_returns_list():
    """semantic_search() returns a list."""
    from backend.storage.search import semantic_search

    with patch("backend.storage.search.get_db") as mock_get_db:
        mock_db = AsyncMock()
        mock_db.execute.return_value = MagicMock(fetchall=AsyncMock(return_value=[]))
        mock_db.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db.__aexit__ = AsyncMock(return_value=None)
        mock_get_db.return_value = mock_db

        with patch("backend.storage.embeddings.get_embedder") as mock_embedder:
            mock_embedder.return_value.embed_text = AsyncMock(return_value=MagicMock())

            result = await semantic_search("test query")
            assert isinstance(result, list)


@pytest.mark.asyncio
async def test_semantic_search_returns_similarity_scores():
    """semantic_search() computes cosine similarity for each match."""
    import numpy as np
    from backend.storage.search import semantic_search

    stored_embedding = np.ones(384, dtype=np.float32).tobytes()

    mock_rows = [
        {
            "segment_id": 1,
            "embedding": stored_embedding,
            "meeting_id": "m1",
            "speaker_label": "SPEAKER_00",
            "speaker_name": None,
            "text": "Xin chào thế giới",
            "start_time": 0.0,
            "end_time": 1.5,
            "language": "vi",
            "meeting_title": "Test Meeting",
            "started_at": "2026-04-13T10:00:00",
        }
    ]

    with patch("backend.storage.search.get_db") as mock_get_db:
        mock_db = AsyncMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall = AsyncMock(return_value=mock_rows)
        mock_db.execute.return_value = mock_cursor
        mock_db.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db.__aexit__ = AsyncMock(return_value=None)
        mock_get_db.return_value = mock_db

        # Query embedding matching stored (cosine sim = 1.0)
        with patch("backend.storage.embeddings.get_embedder") as mock_get_emb:
            mock_embedder = MagicMock()
            mock_embedder.embed_text = AsyncMock(return_value=np.ones(384, dtype=np.float32))
            mock_get_emb.return_value = mock_embedder

            result = await semantic_search("Xin chào", threshold=0.3)

            assert len(result) == 1
            assert "similarity" in result[0]
            assert result[0]["similarity"] > 0.9


@pytest.mark.asyncio
async def test_semantic_search_filters_by_language():
    """semantic_search() applies language filter in SQL."""
    import numpy as np
    from backend.storage.search import semantic_search

    with patch("backend.storage.search.get_db") as mock_get_db:
        mock_db = AsyncMock()
        mock_db.execute.return_value = MagicMock(fetchall=AsyncMock(return_value=[]))
        mock_db.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db.__aexit__ = AsyncMock(return_value=None)
        mock_get_db.return_value = mock_db

        with patch("backend.storage.embeddings.get_embedder") as mock_get_emb:
            mock_embedder = MagicMock()
            mock_embedder.embed_text = AsyncMock(return_value=np.ones(384, dtype=np.float32))
            mock_get_emb.return_value = mock_embedder

            await semantic_search("test", language="en")

            call_args = mock_db.execute.call_args
            sql = call_args[0][0]
            params = call_args[0][1]
            assert "AND ts.language = ?" in sql
            assert "en" in params


@pytest.mark.asyncio
async def test_semantic_search_returns_empty_on_embedding_error():
    """semantic_search() returns empty list when embedding fails."""
    from backend.storage.search import semantic_search

    with patch("backend.storage.search.get_db") as mock_get_db:
        mock_db = AsyncMock()
        mock_db.execute.return_value = MagicMock(fetchall=AsyncMock(return_value=[]))
        mock_db.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db.__aexit__ = AsyncMock(return_value=None)
        mock_get_db.return_value = mock_db

        with patch("backend.storage.embeddings.get_embedder") as mock_get_emb:
            mock_get_emb.side_effect = RuntimeError("Model load failed")

            result = await semantic_search("test query")
            assert result == []


@pytest.mark.asyncio
async def test_semantic_search_respects_threshold():
    """semantic_search() filters out results below threshold."""
    import numpy as np
    from backend.storage.search import semantic_search

    # Stored embedding: all zeros (orthogonal to query)
    stored_embedding = np.zeros(384, dtype=np.float32).tobytes()

    mock_rows = [
        {
            "segment_id": 1,
            "embedding": stored_embedding,
            "meeting_id": "m1",
            "speaker_label": "SPEAKER_00",
            "speaker_name": None,
            "text": "Silent segment",
            "start_time": 0.0,
            "end_time": 1.5,
            "language": "vi",
            "meeting_title": "Test",
            "started_at": "2026-04-13",
        }
    ]

    with patch("backend.storage.search.get_db") as mock_get_db:
        mock_db = AsyncMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall = AsyncMock(return_value=mock_rows)
        mock_db.execute.return_value = mock_cursor
        mock_db.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db.__aexit__ = AsyncMock(return_value=None)
        mock_get_db.return_value = mock_db

        with patch("backend.storage.embeddings.get_embedder") as mock_get_emb:
            mock_embedder = MagicMock()
            # Query embedding is all ones
            mock_embedder.embed_text = AsyncMock(return_value=np.ones(384, dtype=np.float32))
            mock_get_emb.return_value = mock_embedder

            # Very high threshold should filter out all results
            result = await semantic_search("test", threshold=0.99)
            assert len(result) == 0
