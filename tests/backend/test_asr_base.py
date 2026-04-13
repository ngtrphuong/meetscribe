"""Tests for ASR base classes and engine factory."""

import pytest
from backend.asr.base import TranscriptSegment
from backend.asr.engine_factory import ASREngineFactory


def test_transcript_segment_to_dict():
    seg = TranscriptSegment(
        text="Xin chào",
        start_time=1.0,
        end_time=2.5,
        confidence=0.92,
        language="vi",
        speaker="SPEAKER_00",
        source="live",
    )
    d = seg.to_dict()
    assert d["text"] == "Xin chào"
    assert d["start_time"] == 1.0
    assert d["language"] == "vi"
    assert d["speaker"] == "SPEAKER_00"


def test_transcript_segment_defaults():
    seg = TranscriptSegment(text="Test", start_time=0.0, end_time=1.0)
    assert seg.confidence == 0.9
    assert seg.language == "vi"
    assert seg.is_final is True
    assert seg.source == "live"
    assert seg.speaker is None


def test_engine_factory_list_engines():
    engines = ASREngineFactory.list_engines()
    names = [e["name"] for e in engines]
    assert "parakeet-vi" in names
    assert "faster-whisper" in names
    assert "vibevoice" in names


def test_engine_factory_unknown_raises():
    with pytest.raises(ValueError, match="Unknown ASR engine"):
        ASREngineFactory.create("nonexistent-engine")
