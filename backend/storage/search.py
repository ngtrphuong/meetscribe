"""Full-text search (FTS5) and semantic search for MeetScribe transcripts.

Two search modes:
  fts      — SQLite FTS5 (fast, keyword match, Vietnamese tokenization via trigram)
  semantic — sentence-transformers cosine similarity against stored embeddings

File: backend/storage/search.py
"""

from __future__ import annotations

from typing import Optional

import structlog

from backend.database import get_db

logger = structlog.get_logger(__name__)


async def fts_search(
    query: str,
    language: Optional[str] = None,
    limit: int = 50,
) -> list[dict]:
    """Full-text search using SQLite FTS5.

    Args:
        query: Search terms (supports FTS5 query syntax)
        language: Filter by language (vi, en, or None for all)
        limit: Max results

    Returns:
        List of segment dicts with meeting_id, text, start_time, rank
    """
    # Use FTS5 MATCH — wrap in quotes to treat as phrase
    fts_query = f'"{query}"' if " " in query else query

    lang_filter = "AND ts.language = ?" if language else ""
    params: list = [fts_query]
    if language:
        params.append(language)
    params.append(limit)

    sql = f"""
        SELECT
            ts.id,
            ts.meeting_id,
            ts.speaker_label,
            ts.speaker_name,
            ts.text,
            ts.start_time,
            ts.end_time,
            ts.language,
            m.title as meeting_title,
            m.started_at,
            bm25(segments_fts) AS rank
        FROM segments_fts
        JOIN transcript_segments ts ON segments_fts.rowid = ts.id
        JOIN meetings m ON ts.meeting_id = m.id
        WHERE segments_fts MATCH ?
        {lang_filter}
        ORDER BY rank
        LIMIT ?
    """

    try:
        async with get_db() as db:
            cursor = await db.execute(sql, params)
            rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    except Exception as exc:
        logger.error("FTS search error", query=query, error=str(exc))
        return []


async def semantic_search(
    query: str,
    language: Optional[str] = None,
    limit: int = 20,
    threshold: float = 0.5,
) -> list[dict]:
    """Semantic search using sentence-transformers embeddings.

    Computes cosine similarity between query embedding and stored
    segment embeddings. Slower than FTS but finds paraphrases.

    Args:
        query: Natural language query
        language: Filter by language
        limit: Max results
        threshold: Minimum cosine similarity (0.0–1.0)

    Returns:
        List of segment dicts with similarity score
    """
    try:
        from backend.storage.embeddings import get_embedder
        embedder = get_embedder()
        query_embedding = await embedder.embed_text(query)
    except Exception as exc:
        logger.error("Embedding query failed", error=str(exc))
        return []

    # Load all stored embeddings and compute similarity in Python
    # (For large corpora, use a vector DB like Chroma or pgvector)
    lang_filter = "AND ts.language = ?" if language else ""
    params: list = []
    if language:
        params.append(language)

    sql = f"""
        SELECT
            se.segment_id,
            se.embedding,
            ts.meeting_id,
            ts.speaker_label,
            ts.speaker_name,
            ts.text,
            ts.start_time,
            ts.end_time,
            ts.language,
            m.title as meeting_title,
            m.started_at
        FROM segment_embeddings se
        JOIN transcript_segments ts ON se.segment_id = ts.id
        JOIN meetings m ON ts.meeting_id = m.id
        WHERE 1=1 {lang_filter}
    """

    try:
        async with get_db() as db:
            cursor = await db.execute(sql, params)
            rows = await cursor.fetchall()
    except Exception as exc:
        logger.error("Semantic search DB error", error=str(exc))
        return []

    if not rows:
        return []

    import numpy as np

    results = []
    for row in rows:
        row_dict = dict(row)
        emb_bytes = row_dict.pop("embedding")
        if not emb_bytes:
            continue

        try:
            stored = np.frombuffer(emb_bytes, dtype=np.float32)
            score = float(np.dot(query_embedding, stored) /
                         (np.linalg.norm(query_embedding) * np.linalg.norm(stored) + 1e-8))
            if score >= threshold:
                row_dict["similarity"] = round(score, 4)
                results.append(row_dict)
        except Exception:
            continue

    # Sort by similarity descending, limit results
    results.sort(key=lambda x: x["similarity"], reverse=True)
    return results[:limit]
