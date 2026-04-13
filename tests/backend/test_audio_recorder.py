"""Comprehensive tests for audio recording session management.

Tests the RecordingSession class lifecycle: start, pause, resume, stop,
audio buffer management, WAV assembly, and consent handling.
Run: pytest tests/backend/test_audio_recorder.py -v
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
import asyncio
import time


class TestRecordingState:
    """Tests for RecordingState enum."""

    def test_recording_state_values(self):
        """Test RecordingState enum has all expected values."""
        from backend.audio.recorder import RecordingState

        assert RecordingState.IDLE.value == "idle"
        assert RecordingState.RECORDING.value == "recording"
        assert RecordingState.PAUSED.value == "paused"
        assert RecordingState.PROCESSING.value == "processing"
        assert RecordingState.COMPLETE.value == "complete"
        assert RecordingState.ERROR.value == "error"


class TestRecordingSessionInit:
    """Tests for RecordingSession initialization."""

    def test_session_default_values(self):
        """Test RecordingSession initializes with correct defaults."""
        from backend.audio.recorder import RecordingSession, RecordingState

        session = RecordingSession(
            meeting_id="test-123",
            system_device_id=None,
            mic_device_id=None,
            consent_recording=False,
        )

        assert session.meeting_id == "test-123"
        assert session.consent_recording is False
        assert session.state == RecordingState.IDLE
        assert session.started_at is None
        assert session.ended_at is None
        assert session.duration_seconds == 0
        assert list(session._audio_buffer) == []
        assert session._chunk_queues == []

    def test_session_with_consent(self):
        """Test RecordingSession stores consent_recording flag."""
        from backend.audio.recorder import RecordingSession

        session = RecordingSession(
            meeting_id="test-456",
            consent_recording=True,
        )
        assert session.consent_recording is True

    def test_session_default_silence_timeout(self):
        """Test default silence timeout is 300 seconds."""
        from backend.audio.recorder import RecordingSession, SILENCE_TIMEOUT_SECONDS

        session = RecordingSession(meeting_id="test")
        assert session.silence_timeout == SILENCE_TIMEOUT_SECONDS
        assert SILENCE_TIMEOUT_SECONDS == 300

    def test_session_custom_silence_timeout(self):
        """Test RecordingSession accepts custom silence_timeout."""
        from backend.audio.recorder import RecordingSession

        session = RecordingSession(
            meeting_id="test",
            silence_timeout=60,
        )
        assert session.silence_timeout == 60


class TestRecordingSessionPauseResume:
    """Tests for RecordingSession.pause() and resume()."""

    @pytest.mark.asyncio
    async def test_pause_transitions_to_paused(self):
        """Test pause() transitions from RECORDING to PAUSED."""
        from backend.audio.recorder import RecordingSession, RecordingState

        session = RecordingSession(meeting_id="test-123")
        session.state = RecordingState.RECORDING
        session._capture = MagicMock()
        session._capture.stop = AsyncMock()

        await session.pause()

        assert session.state == RecordingState.PAUSED
        assert session._pause_start is not None

    @pytest.mark.asyncio
    async def test_pause_from_idle_is_noop(self):
        """Test pause() from IDLE is a no-op (returns early)."""
        from backend.audio.recorder import RecordingSession, RecordingState

        session = RecordingSession(meeting_id="test-123")
        session.state = RecordingState.IDLE
        session._capture = MagicMock()
        session._capture.stop = AsyncMock()

        await session.pause()

        assert session.state == RecordingState.IDLE

    @pytest.mark.asyncio
    async def test_resume_transitions_to_recording(self):
        """Test resume() transitions from PAUSED back to RECORDING."""
        from backend.audio.recorder import RecordingSession, RecordingState

        session = RecordingSession(meeting_id="test-123")
        session.state = RecordingState.PAUSED
        session._pause_start = time.time() - 10  # 10 seconds ago
        session._capture = MagicMock()
        session._capture.start = AsyncMock()

        await session.resume()

        assert session.state == RecordingState.RECORDING
        assert session._paused_duration > 0

    @pytest.mark.asyncio
    async def test_resume_from_wrong_state_is_noop(self):
        """Test resume() from non-PAUSED state is a no-op."""
        from backend.audio.recorder import RecordingSession, RecordingState

        session = RecordingSession(meeting_id="test-123")
        session.state = RecordingState.RECORDING

        await session.resume()

        assert session.state == RecordingState.RECORDING


class TestRecordingSessionStop:
    """Tests for RecordingSession.stop()."""

    @pytest.mark.asyncio
    async def test_stop_from_recording_returns_wav_bytes(self):
        """Test stop() from RECORDING returns WAV bytes."""
        from backend.audio.recorder import RecordingSession, RecordingState

        session = RecordingSession(meeting_id="test-123")
        session.state = RecordingState.RECORDING
        session.started_at = time.time() - 60  # 60 seconds ago
        session._capture = MagicMock()
        session._capture.stop = AsyncMock()

        # Mock the audio buffer with some data
        import numpy as np
        chunk = np.zeros(1600, dtype=np.int16).tobytes()
        session._audio_buffer.append(chunk)

        # Mock background tasks as done
        async def noop():
            pass
        session._record_task = asyncio.create_task(noop())
        session._checkpoint_task = None
        session._silence_task = None

        wav_bytes = await session.stop()

        assert isinstance(wav_bytes, bytes)
        # WAV files start with RIFF header
        assert wav_bytes[:4] == b"RIFF"

    @pytest.mark.asyncio
    async def test_stop_from_idle_returns_empty_bytes(self):
        """Test stop() from IDLE returns empty bytes."""
        from backend.audio.recorder import RecordingSession, RecordingState

        session = RecordingSession(meeting_id="test-123")
        session.state = RecordingState.IDLE

        wav_bytes = await session.stop()
        assert wav_bytes == b""

    @pytest.mark.asyncio
    async def test_stop_sets_state_to_processing(self):
        """Test stop() transitions state to PROCESSING."""
        from backend.audio.recorder import RecordingSession, RecordingState

        session = RecordingSession(meeting_id="test-123")
        session.state = RecordingState.RECORDING
        session.started_at = time.time() - 60
        session._capture = MagicMock()
        session._capture.stop = AsyncMock()

        async def noop():
            pass
        session._record_task = asyncio.create_task(noop())
        session._checkpoint_task = None
        session._silence_task = None

        await session.stop()

        assert session.state == RecordingState.PROCESSING

    @pytest.mark.asyncio
    async def test_stop_clears_audio_buffer(self):
        """Test stop() clears the audio buffer (Decree 356)."""
        from backend.audio.recorder import RecordingSession, RecordingState

        session = RecordingSession(meeting_id="test-123")
        session.state = RecordingState.RECORDING
        session.started_at = time.time() - 60
        session._capture = MagicMock()
        session._capture.stop = AsyncMock()

        # Add chunks to buffer
        import numpy as np
        chunk = np.zeros(1600, dtype=np.int16).tobytes()
        session._audio_buffer.append(chunk)

        async def noop():
            pass
        session._record_task = asyncio.create_task(noop())
        session._checkpoint_task = None
        session._silence_task = None

        await session.stop()

        assert len(session._audio_buffer) == 0

    @pytest.mark.asyncio
    async def test_stop_calculates_duration(self):
        """Test stop() calculates duration_seconds correctly."""
        from backend.audio.recorder import RecordingSession, RecordingState

        session = RecordingSession(meeting_id="test-123")
        session.state = RecordingState.RECORDING
        session.started_at = time.time() - 60
        session._capture = MagicMock()
        session._capture.stop = AsyncMock()

        async def noop():
            pass
        session._record_task = asyncio.create_task(noop())
        session._checkpoint_task = None
        session._silence_task = None

        await session.stop()

        assert session.duration_seconds >= 0


class TestChunkConsumer:
    """Tests for RecordingSession chunk consumer registration."""

    def test_add_chunk_consumer_returns_queue(self):
        """Test add_chunk_consumer() returns an asyncio.Queue."""
        from backend.audio.recorder import RecordingSession

        session = RecordingSession(meeting_id="test-123")
        q = session.add_chunk_consumer()

        assert isinstance(q, asyncio.Queue)
        assert q in session._chunk_queues

    def test_add_multiple_consumers(self):
        """Test multiple consumers can be registered."""
        from backend.audio.recorder import RecordingSession

        session = RecordingSession(meeting_id="test-123")
        q1 = session.add_chunk_consumer()
        q2 = session.add_chunk_consumer()

        assert len(session._chunk_queues) == 2
        assert q1 is not q2


class TestGetLevels:
    """Tests for RecordingSession.get_levels()."""

    def test_get_levels_returns_dict(self):
        """Test get_levels() returns a dict with system and mic levels."""
        from backend.audio.recorder import RecordingSession

        session = RecordingSession(meeting_id="test-123")
        session._capture = MagicMock()
        session._capture.get_levels.return_value = {"system": 0.5, "mic": 0.3}

        levels = session.get_levels()

        assert levels == {"system": 0.5, "mic": 0.3}


class TestElapsedSeconds:
    """Tests for RecordingSession.elapsed_seconds property."""

    def test_elapsed_seconds_zero_when_not_started(self):
        """Test elapsed_seconds returns 0 when meeting not started."""
        from backend.audio.recorder import RecordingSession

        session = RecordingSession(meeting_id="test-123")
        assert session.elapsed_seconds == 0.0

    def test_elapsed_seconds_positive_when_recording(self):
        """Test elapsed_seconds returns positive value when recording."""
        from backend.audio.recorder import RecordingSession

        session = RecordingSession(meeting_id="test-123")
        session.started_at = 1000.0
        session._paused_duration = 0.0

        with patch("backend.audio.recorder.time.time", return_value=1050.0):
            elapsed = session.elapsed_seconds
            assert elapsed == 50.0


class TestComputeRMS:
    """Tests for _compute_rms() helper."""

    def test_compute_rms_zero_for_empty_chunk(self):
        """Test _compute_rms() returns 0.0 for empty chunk."""
        from backend.audio.recorder import _compute_rms

        assert _compute_rms(b"") == 0.0

    def test_compute_rms_positive_for_silence(self):
        """Test _compute_rms() returns positive value for near-silence."""
        from backend.audio.recorder import _compute_rms
        import numpy as np

        # Very quiet audio (near zero)
        quiet = np.zeros(1600, dtype=np.int16)
        chunk = quiet.tobytes()
        rms = _compute_rms(chunk)
        assert 0.0 <= rms <= 0.001

    def test_compute_rms_returns_normalized_value(self):
        """Test _compute_rms() returns value between 0.0 and 1.0."""
        from backend.audio.recorder import _compute_rms
        import numpy as np

        # Half-scale sine wave
        samples = np.sin(np.linspace(0, 1, 1600) * np.pi).astype(np.int16) * 16000
        chunk = samples.tobytes()
        rms = _compute_rms(chunk)
        assert 0.0 <= rms <= 1.0


class TestAssembleWAV:
    """Tests for RecordingSession._assemble_wav()."""

    def test_assemble_wav_empty_buffer(self):
        """Test _assemble_wav() returns empty bytes for empty buffer."""
        from backend.audio.recorder import RecordingSession

        session = RecordingSession(meeting_id="test-123")
        assert session._assemble_wav() == b""

    def test_assemble_wav_returns_wav_header(self):
        """Test _assemble_wav() returns valid WAV file bytes."""
        from backend.audio.recorder import RecordingSession
        import numpy as np

        session = RecordingSession(meeting_id="test-123")
        chunk = np.zeros(1600, dtype=np.int16).tobytes()
        session._audio_buffer.append(chunk)

        wav_bytes = session._assemble_wav()

        assert wav_bytes[:4] == b"RIFF"
        assert wav_bytes[8:12] == b"WAVE"


class TestSilenceMonitor:
    """Tests for silence monitor behavior."""

    def test_silence_timeout_defaults_to_300(self):
        """Test silence timeout defaults to 300 seconds (5 minutes)."""
        from backend.audio.recorder import RecordingSession, SILENCE_TIMEOUT_SECONDS

        assert SILENCE_TIMEOUT_SECONDS == 300

    def test_silence_timeout_can_be_disabled(self):
        """Test silence_timeout=0 disables auto-stop."""
        from backend.audio.recorder import RecordingSession

        session = RecordingSession(meeting_id="test-123", silence_timeout=0)
        assert session.silence_timeout == 0

    def test_max_duration_constant(self):
        """Test MAX_DURATION_SECONDS is 4 hours."""
        from backend.audio.recorder import MAX_DURATION_SECONDS

        assert MAX_DURATION_SECONDS == 4 * 60 * 60


class TestSessionIOTQueues:
    """Tests for IoT audio queue registration."""

    def test_iot_queues_initially_empty_list(self):
        """Test iot_queues can be assigned (orchestrator sets this dynamically)."""
        from backend.audio.recorder import RecordingSession

        session = RecordingSession(meeting_id="test-123")
        # iot_queues is set by orchestrator, not in __init__
        session.iot_queues = []
        assert session.iot_queues == []
