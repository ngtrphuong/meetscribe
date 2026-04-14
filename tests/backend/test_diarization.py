"""Comprehensive tests for diarization modules.

Tests live_diarization.py, offline_diarization.py, and speaker_profiles.py.
Run: pytest tests/backend/test_diarization.py -v
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
import asyncio


class TestSpeakerProfileManagerAssign:
    """Tests for SpeakerProfileManager name assignment."""

    def test_assign_name_and_retrieve(self):
        """assign_name() and get_name() work bidirectionally."""
        from backend.diarization.speaker_profiles import SpeakerProfileManager

        mgr = SpeakerProfileManager()
        mgr.assign_name("SPEAKER_00", "Nguyễn Văn A")

        assert mgr.get_name("SPEAKER_00") == "Nguyễn Văn A"
        assert mgr.get_label("Nguyễn Văn A") == "SPEAKER_00"

    def test_get_name_unknown_label_returns_none(self):
        """get_name() returns None for unknown label."""
        from backend.diarization.speaker_profiles import SpeakerProfileManager

        mgr = SpeakerProfileManager()
        assert mgr.get_name("SPEAKER_99") is None

    def test_get_label_unknown_name_returns_none(self):
        """get_label() returns None for unknown name."""
        from backend.diarization.speaker_profiles import SpeakerProfileManager

        mgr = SpeakerProfileManager()
        assert mgr.get_label("Unknown Person") is None


class TestSpeakerProfileManagerVoiceprint:
    """Tests for voiceprint management (Decree 356)."""

    @pytest.mark.asyncio
    async def test_save_voiceprint_returns_uuid(self, tmp_path):
        """save_voiceprint() returns a UUID string."""
        from backend.diarization.speaker_profiles import SpeakerProfileManager
        from backend.database import init_db

        mock_cfg = MagicMock()
        mock_cfg.database_path = tmp_path / "test.db"
        mock_cfg.data_dir = tmp_path
        mock_cfg.db_key = "testkey123456789012345678901234"

        with patch("backend.config.settings", mock_cfg):
            with patch("backend.database.settings", mock_cfg):
                await init_db()

                mgr = SpeakerProfileManager()
                result = await mgr.save_voiceprint(
                    speaker_name="Nguyễn Văn A",
                    embedding=b"\x00\x01\x02\x03",
                    meeting_id="meeting-123",
                )

                assert isinstance(result, str)
                assert len(result) > 0

    @pytest.mark.asyncio
    async def test_load_voiceprints_returns_list(self, tmp_path):
        """load_voiceprints() returns a list of dicts."""
        from backend.diarization.speaker_profiles import SpeakerProfileManager
        from backend.database import init_db

        mock_cfg = MagicMock()
        mock_cfg.database_path = tmp_path / "test.db"
        mock_cfg.data_dir = tmp_path
        mock_cfg.db_key = "testkey123456789012345678901234"

        with patch("backend.config.settings", mock_cfg):
            with patch("backend.database.settings", mock_cfg):
                await init_db()

                mgr = SpeakerProfileManager()
                result = await mgr.load_voiceprints()

                assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_delete_voiceprint_returns_true_when_found(self, tmp_path):
        """delete_voiceprint() returns True when voiceprint exists."""
        from backend.diarization.speaker_profiles import SpeakerProfileManager
        from backend.database import init_db

        mock_cfg = MagicMock()
        mock_cfg.database_path = tmp_path / "test.db"
        mock_cfg.data_dir = tmp_path
        mock_cfg.db_key = "testkey123456789012345678901234"

        with patch("backend.config.settings", mock_cfg):
            with patch("backend.database.settings", mock_cfg):
                await init_db()

                mgr = SpeakerProfileManager()
                vpid = await mgr.save_voiceprint(
                    speaker_name="Test Speaker",
                    embedding=b"fake_embedding_data",
                    meeting_id="meeting-123",
                )

                deleted = await mgr.delete_voiceprint(vpid)
                assert deleted is True

    @pytest.mark.asyncio
    async def test_delete_voiceprint_returns_false_when_not_found(self, tmp_path):
        """delete_voiceprint() returns False for unknown ID."""
        from backend.diarization.speaker_profiles import SpeakerProfileManager
        from backend.database import init_db

        mock_cfg = MagicMock()
        mock_cfg.database_path = tmp_path / "test.db"
        mock_cfg.data_dir = tmp_path
        mock_cfg.db_key = "testkey123456789012345678901234"

        with patch("backend.config.settings", mock_cfg):
            with patch("backend.database.settings", mock_cfg):
                await init_db()

                mgr = SpeakerProfileManager()
                deleted = await mgr.delete_voiceprint("nonexistent-vpid")
                assert deleted is False


class TestSpeakerProfileManagerIdentify:
    """Tests for speaker identification via embeddings."""

    def test_identify_speaker_returns_name_above_threshold(self):
        """identify_speaker() returns speaker name when score >= threshold."""
        from backend.diarization.speaker_profiles import SpeakerProfileManager
        import numpy as np

        mgr = SpeakerProfileManager()

        # Create two embeddings: query and stored
        query_emb = np.random.randn(384).astype(np.float32)
        stored_emb = query_emb.copy()  # Perfect match

        result = mgr.identify_speaker(
            query_emb,
            [{"name": "Nguyễn Văn A", "embedding": stored_emb.tobytes()}],
            threshold=0.5,
        )

        assert result == "Nguyễn Văn A"

    def test_identify_speaker_returns_none_below_threshold(self):
        """identify_speaker() returns None when score < threshold."""
        from backend.diarization.speaker_profiles import SpeakerProfileManager
        import numpy as np

        mgr = SpeakerProfileManager()

        # Orthogonal embeddings (cosine similarity ~= 0)
        query_emb = np.ones(384, dtype=np.float32)
        stored_emb = np.zeros(384, dtype=np.float32)

        result = mgr.identify_speaker(
            query_emb,
            [{"name": "Nguyễn Văn A", "embedding": stored_emb.tobytes()}],
            threshold=0.75,
        )

        assert result is None

    def test_identify_speaker_returns_none_when_no_voiceprints(self):
        """identify_speaker() returns None when known_voiceprints is empty."""
        from backend.diarization.speaker_profiles import SpeakerProfileManager
        import numpy as np

        mgr = SpeakerProfileManager()
        query_emb = np.ones(384, dtype=np.float32)

        result = mgr.identify_speaker(query_emb, [], threshold=0.75)
        assert result is None


class TestLiveDiarizationInit:
    """Tests for LiveDiarization initialization."""

    def test_init_default_values(self):
        """Test default values for LiveDiarization."""
        from backend.diarization.live_diarization import LiveDiarization

        diar = LiveDiarization()
        assert diar.num_speakers is None
        assert diar._pipeline is None
        assert diar._running is False
        assert isinstance(diar.speaker_queue, asyncio.Queue)

    def test_init_with_num_speakers(self):
        """Test custom num_speakers parameter."""
        from backend.diarization.live_diarization import LiveDiarization

        diar = LiveDiarization(num_speakers=3)
        assert diar.num_speakers == 3


class TestLiveDiarizationStartStop:
    """Tests for LiveDiarization start/stop lifecycle."""

    @pytest.mark.asyncio
    async def test_start_creates_task(self):
        """start() creates and starts a background task."""
        from backend.diarization.live_diarization import LiveDiarization

        diar = LiveDiarization()
        audio_q = asyncio.Queue()

        await diar.start(audio_q)

        assert diar._task is not None
        assert diar._running is True

        await diar.stop()
        # Task should be done after stop

    @pytest.mark.asyncio
    async def test_stop_cancels_task(self):
        """stop() cancels the background task."""
        from backend.diarization.live_diarization import LiveDiarization

        diar = LiveDiarization()
        audio_q = asyncio.Queue()

        await diar.start(audio_q)
        await diar.stop()

        assert diar._running is False


class TestLiveDiarizationStubPipeline:
    """Tests for the stub pipeline when diart is unavailable."""

    @pytest.mark.asyncio
    async def test_stub_pipeline_labels_all_as_speaker_00(self):
        """Stub pipeline labels all audio as SPEAKER_00."""
        from backend.diarization.live_diarization import LiveDiarization
        import time

        diar = LiveDiarization()
        audio_q = asyncio.Queue()
        await diar.start(audio_q)

        # Put a chunk in
        chunk = b"\x00" * 6400  # 100ms at 16kHz mono 16bit
        await audio_q.put(chunk)

        # Wait for stub to process
        await asyncio.sleep(0.2)

        await diar.stop()

        # Speaker queue should have at least one event
        events = []
        while not diar.speaker_queue.empty():
            events.append(await diar.speaker_queue.get())

        assert len(events) >= 1
        assert all(e["speaker"] == "SPEAKER_00" for e in events)


class TestOfflineDiarizationInit:
    """Tests for OfflineDiarization initialization."""

    def test_init_default_values(self):
        """Test default values for OfflineDiarization."""
        from backend.diarization.offline_diarization import OfflineDiarization

        diar = OfflineDiarization()
        assert diar.num_speakers is None
        assert diar._pipeline is None

    def test_init_with_params(self):
        """Test custom auth_token and num_speakers."""
        from backend.diarization.offline_diarization import OfflineDiarization

        diar = OfflineDiarization(num_speakers=4, auth_token="test-token")
        assert diar.num_speakers == 4
        assert diar.auth_token == "test-token"


class TestOfflineDiarizationLoad:
    """Tests for OfflineDiarization._load_pipeline()."""

    def test_load_logs_warning_when_pyannote_unavailable(self):
        """_load_pipeline() logs warning when pyannote.audio not installed."""
        from backend.diarization.offline_diarization import OfflineDiarization

        diar = OfflineDiarization()

        with patch.dict("sys.modules", pyannote={}):
            with patch("backend.diarization.offline_diarization.logger") as mock_logger:
                diar._load_pipeline()

                # Should log warning about pyannote not installed
                mock_logger.warning.assert_called()


class TestOfflineDiarizationDiarize:
    """Tests for OfflineDiarization.diarize()."""

    @pytest.mark.asyncio
    async def test_diarize_returns_empty_when_pipeline_not_loaded(self):
        """diarize() returns empty list when pipeline not loaded."""
        from backend.diarization.offline_diarization import OfflineDiarization

        diar = OfflineDiarization()
        diar._pipeline = None  # Not loaded

        result = await diar.diarize("/fake/path.wav")
        assert result == []
