"""Search API endpoint.

GET /api/search?q={query}&type=fts|semantic&language=vi

File: backend/api/search.py
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Query

router = APIRouter()


@router.get("")
async def search(
    q: str = Query(..., min_length=1, description="Search query"),
    type: str = Query("fts", description="fts (full-text) or semantic"),
    language: Optional[str] = Query(None, description="vi or en"),
    limit: int = Query(50, ge=1, le=200),
):
    """Search meeting transcripts using FTS5 or semantic embedding similarity."""
    if type == "semantic":
        from backend.storage.search import semantic_search
        results = await semantic_search(q, language=language, limit=limit)
    else:
        from backend.storage.search import fts_search
        results = await fts_search(q, language=language, limit=limit)

    return {"query": q, "type": type, "count": len(results), "results": results}
