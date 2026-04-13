"""Sentence-transformer embeddings for semantic search.

Model: all-MiniLM-L6-v2 (22MB, CPU-friendly, 384-dim embeddings)
Embeddings stored as BLOB (float32 bytes) in segment_embeddings table.

File: backend/storage/embeddings.py
"""

from __future__ import annotations

import asyncio
from typing import Optional

import numpy as np
import structlog

logger = structlog.get_logger(__name__)

DEFAULT_MODEL = "all-MiniLM-L6-v2"
_embedder_instance: Optional["SegmentEmbedder"] = None


def get_embedder() -> "SegmentEmbedder":
    """Return the singleton embedder (loads model on first call)."""
    global _embedder_instance
    if _embedder_instance is None:
        _embedder_instance = SegmentEmbedder()
    return _embedder_instance


class SegmentEmbedder:
    """Generates and stores embeddings for transcript segments."""

    def __init__(self, model_name: str = DEFAULT_MODEL):
        self.model_name = model_name
        self._model = None

    def _load(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            logger.info("Loading sentence-transformer", model=self.model_name)
            self._model = SentenceTransformer(self.model_name)

    async def embed_text(self, text: str) -> np.ndarray:
        """Embed a single text string."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._embed_sync, text)

    def _embed_sync(self, text: str) -> np.ndarray:
        self._load()
        return self._model.encode(text, normalize_embeddings=True).astype(np.float32)

    async def embed_and_store_segment(self, segment_id: int, text: str) -> None:
        """Embed a transcript segment and store in DB."""
        embedding = await self.embed_text(text)
        embedding_bytes = embedding.tobytes()

        from backend.database import get_db
        async with get_db() as db:
            await db.execute(
                """INSERT OR REPLACE INTO segment_embeddings (segment_id, embedding)
                   VALUES (?, ?)""",
                (segment_id, embedding_bytes),
            )
            await db.commit()

    async def embed_meeting_segments(self, meeting_id: str) -> int:
        """Embed all segments for a meeting (batch after POST processing).

        Returns count of segments embedded.
        """
        from backend.database import get_db

        async with get_db() as db:
            cursor = await db.execute(
                "SELECT id, text FROM transcript_segments WHERE meeting_id = ?",
                (meeting_id,),
            )
            segments = await cursor.fetchall()

        count = 0
        for seg in segments:
            try:
                await self.embed_and_store_segment(seg["id"], seg["text"])
                count += 1
            except Exception as exc:
                logger.warning("Embedding failed", segment_id=seg["id"], error=str(exc))

        logger.info("Segments embedded", meeting_id=meeting_id, count=count)
        return count
