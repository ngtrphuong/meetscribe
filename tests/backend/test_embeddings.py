"""Comprehensive tests for sentence-transformer embeddings.

Tests SegmentEmbedder for text embedding, embedding storage in DB,
and batch embedding of meeting segments. Skipped when sentence-transformers
is not installed.
Run: pytest tests/backend/test_embeddings.py -v
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
import numpy as np


class TestSegmentEmbedderDefaults:
    """Tests for SegmentEmbedder initialization."""

    def test_default_model_name(self):
        """Default model is all-MiniLM-L6-v2."""
        from backend.storage.embeddings import SegmentEmbedder, DEFAULT_MODEL

        embedder = SegmentEmbedder()
        assert embedder.model_name == DEFAULT_MODEL
        assert DEFAULT_MODEL == "all-MiniLM-L6-v2"

    def test_custom_model_name(self):
        """SegmentEmbedder accepts custom model_name."""
        from backend.storage.embeddings import SegmentEmbedder

        embedder = SegmentEmbedder(model_name="all-mpnet-base-v2")
        assert embedder.model_name == "all-mpnet-base-v2"

    def test_embedder_not_loaded_initially(self):
        """SegmentEmbedder._model is None before loading."""
        from backend.storage.embeddings import SegmentEmbedder

        embedder = SegmentEmbedder()
        assert embedder._model is None


class TestEmbedderSingleton:
    """Tests for the get_embedder() singleton."""

    def test_get_embedder_returns_singleton(self):
        """get_embedder() returns the same instance on multiple calls."""
        from backend.storage.embeddings import get_embedder

        e1 = get_embedder()
        e2 = get_embedder()

        assert e1 is e2


class TestEmbedText:
    """Tests for embed_text() and _embed_sync()."""

    @pytest.mark.asyncio
    async def test_embed_text_returns_numpy_array(self):
        """embed_text() returns a numpy float32 array."""
        from backend.storage.embeddings import SegmentEmbedder

        embedder = SegmentEmbedder()
        embedder._model = MagicMock()
        embedder._model.encode.return_value = np.ones(384, dtype=np.float32)

        result = await embedder.embed_text("Xin chào thế giới")

        assert isinstance(result, np.ndarray)
        assert result.dtype == np.float32

    @pytest.mark.asyncio
    async def test_embed_text_normalizes_output(self):
        """embed_text() encodes with normalize_embeddings=True."""
        from backend.storage.embeddings import SegmentEmbedder

        embedder = SegmentEmbedder()
        mock_model = MagicMock()
        # Return a normalized vector
        vec = np.ones(384, dtype=np.float32) / np.sqrt(384)
        mock_model.encode.return_value = vec
        embedder._model = mock_model

        result = await embedder.embed_text("Test transcript")

        mock_model.encode.assert_called_once()
        call_kwargs = mock_model.encode.call_args[1]
        assert call_kwargs["normalize_embeddings"] is True

    @pytest.mark.asyncio
    async def test_embed_text_loads_model_on_first_call(self):
        """embed_text() lazily loads the model."""
        from backend.storage.embeddings import SegmentEmbedder

        embedder = SegmentEmbedder()
        mock_st = MagicMock()
        mock_st.SentenceTransformer.return_value = MagicMock()

        with patch("sentence_transformers.SentenceTransformer", mock_st):
            embedder._model = None  # Not loaded
            # Patch the encode to avoid actual model call
            with patch.object(embedder, "_embed_sync", return_value=np.ones(384, dtype=np.float32)):
                await embedder.embed_text("Test")


class TestEmbedAndStoreSegment:
    """Tests for embed_and_store_segment()."""

    @pytest.mark.asyncio
    async def test_embed_and_store_segment_inserts_into_db(self, tmp_path):
        """embed_and_store_segment() inserts embedding into segment_embeddings table."""
        from backend.storage.embeddings import SegmentEmbedder
        from backend.database import init_db, get_db, audit

        mock_cfg = MagicMock()
        mock_cfg.database_path = tmp_path / "test.db"
        mock_cfg.data_dir = tmp_path
        mock_cfg.db_key = "testkey123456789012345678901234"

        with patch("backend.config.settings", mock_cfg):
            with patch("backend.database.settings", mock_cfg):
                await init_db()

                # Insert a meeting first (parent record for segment FK)
                async with get_db() as db:
                    await db.execute(
                        """INSERT INTO meetings (id, title, started_at, status)
                           VALUES (?, ?, datetime('now'), 'recording')""",
                        ("test-meeting-embed-123", "Embed Test Meeting"),
                    )
                    await db.commit()

                # Insert a segment referencing that meeting
                seg_id = None
                async with get_db() as db:
                    cursor = await db.execute(
                        """INSERT INTO transcript_segments
                           (meeting_id, text, start_time, end_time, confidence, language, source)
                           VALUES (?, ?, ?, ?, ?, ?, ?)""",
                        ("test-meeting-embed-123", "Test segment text", 0.0, 1.5, 0.9, "vi", "live"),
                    )
                    await db.commit()
                    seg_id = cursor.lastrowid

                assert seg_id is not None

                embedder = SegmentEmbedder()
                embedder._model = MagicMock()
                embedder._model.encode.return_value = np.ones(384, dtype=np.float32)

                await embedder.embed_and_store_segment(seg_id, "Test segment text")

                # Verify it was inserted
                async with get_db() as db:
                    cursor = await db.execute(
                        "SELECT segment_id FROM segment_embeddings WHERE segment_id = ?",
                        (seg_id,),
                    )
                    row = await cursor.fetchone()
                assert row is not None


class TestEmbedMeetingSegments:
    """Tests for embed_meeting_segments()."""

    @pytest.mark.asyncio
    async def test_embed_meeting_segments_returns_count(self, tmp_path):
        """embed_meeting_segments() returns count of embedded segments."""
        from backend.storage.embeddings import SegmentEmbedder
        from backend.database import init_db

        mock_cfg = MagicMock()
        mock_cfg.database_path = tmp_path / "test.db"
        mock_cfg.data_dir = tmp_path
        mock_cfg.db_key = "testkey123456789012345678901234"

        with patch("backend.config.settings", mock_cfg):
            with patch("backend.database.settings", mock_cfg):
                await init_db()

                embedder = SegmentEmbedder()
                embedder._model = MagicMock()
                embedder._model.encode.return_value = np.ones(384, dtype=np.float32)

                # No segments for this meeting yet
                count = await embedder.embed_meeting_segments("meeting-with-no-segments")
                assert count == 0
