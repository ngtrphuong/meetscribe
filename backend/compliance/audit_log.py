"""Audit log queries for Decree 356 compliance reporting.

The audit_log table is written by backend/database.py::audit().
This module provides read-only query functions for the compliance API.

File: backend/compliance/audit_log.py
"""

from __future__ import annotations

from typing import Optional

from backend.database import get_db
from backend.storage.models import AuditLogEntry


async def get_audit_log(
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    action: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> list[AuditLogEntry]:
    """Query audit log with optional filters."""
    conditions = []
    params: list = []

    if entity_type:
        conditions.append("entity_type = ?")
        params.append(entity_type)
    if entity_id:
        conditions.append("entity_id = ?")
        params.append(entity_id)
    if action:
        conditions.append("action = ?")
        params.append(action)

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    params += [limit, offset]

    sql = f"""
        SELECT * FROM audit_log
        {where}
        ORDER BY performed_at DESC
        LIMIT ? OFFSET ?
    """

    async with get_db() as db:
        cursor = await db.execute(sql, params)
        rows = await cursor.fetchall()

    return [AuditLogEntry(**dict(r)) for r in rows]
