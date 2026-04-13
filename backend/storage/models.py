"""Pydantic data models for MeetScribe storage layer.

These models mirror the DB schema from CLAUDE.md §6 and are used for
API serialization and internal data transfer.
"""

from __future__ import annotations

import datetime
from typing import Optional

from pydantic import BaseModel, Field


class Meeting(BaseModel):
    id: str
    title: str
    started_at: datetime.datetime
    ended_at: Optional[datetime.datetime] = None
    duration_seconds: Optional[int] = None
    audio_retained: bool = False
    audio_file_path: Optional[str] = None
    primary_language: str = "vi"
    asr_live_engine: Optional[str] = None
    asr_post_engine: Optional[str] = None
    llm_provider: Optional[str] = None
    template_name: Optional[str] = None
    consent_recording: bool = False
    consent_voiceprint: bool = False
    status: str = "recording"
    created_at: Optional[datetime.datetime] = None
    updated_at: Optional[datetime.datetime] = None


class TranscriptSegmentDB(BaseModel):
    id: Optional[int] = None
    meeting_id: str
    speaker_label: Optional[str] = None
    speaker_name: Optional[str] = None
    text: str
    start_time: float
    end_time: float
    confidence: Optional[float] = None
    language: Optional[str] = None
    source: str = "live"
    created_at: Optional[datetime.datetime] = None


class Summary(BaseModel):
    id: Optional[int] = None
    meeting_id: str
    template_name: Optional[str] = None
    content: str
    llm_provider: Optional[str] = None
    llm_model: Optional[str] = None
    generated_at: Optional[datetime.datetime] = None


class ActionItem(BaseModel):
    id: Optional[int] = None
    meeting_id: str
    description: str
    owner: Optional[str] = None
    deadline: Optional[str] = None
    status: str = "open"
    created_at: Optional[datetime.datetime] = None


class MeetingDetail(Meeting):
    """Meeting with embedded summary and action items."""
    summary: Optional[Summary] = None
    action_items: list[ActionItem] = Field(default_factory=list)
    segment_count: int = 0


class AuditLogEntry(BaseModel):
    id: Optional[int] = None
    action: str
    entity_type: str
    entity_id: str
    details: Optional[str] = None
    performed_at: Optional[datetime.datetime] = None
