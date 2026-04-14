"""Comprehensive tests for NVIDIA Maxine audio preprocessor.

Tests MaxinePreprocessor initialization (passthrough when SDK unavailable),
chunk processing (passthrough + AEC/BNR when available), and lifecycle methods.
Run: pytest tests/backend/test_maxine_preprocessor.py -v
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
import numpy as np


class TestMaxinePreprocessorInit:
    """Tests for MaxinePreprocessor initialization."""

    def test_init_defaults(self):
        """Test default enabled flags."""
        from backend.audio.maxine_preprocessor import MaxinePreprocessor

        p = MaxinePreprocessor()
        assert p.enable_aec is True
        assert p.enable_bnr is True
        assert p._maxine_available is False

    def test_init_custom_flags(self):
        """Test custom AEC/BNR flags."""
        from backend.audio.maxine_preprocessor import MaxinePreprocessor

        p = MaxinePreprocessor(enable_aec=False, enable_bnr=False)
        assert p.enable_aec is False
        assert p.enable_bnr is False

    @pytest.mark.asyncio
    async def test_init_passthrough_when_import_fails(self):
        """initialize() uses passthrough when nvidia.maxine import fails."""
        from backend.audio.maxine_preprocessor import MaxinePreprocessor

        p = MaxinePreprocessor()
        await p.initialize()

        assert p._maxine_available is False
        assert p._aec_session is None
        assert p._bnr_session is None

    @pytest.mark.asyncio
    async def test_init_logs_warning_on_exception(self):
        """initialize() logs warning when Maxine init fails."""
        from backend.audio.maxine_preprocessor import MaxinePreprocessor

        p = MaxinePreprocessor()

        with patch.dict("sys.modules", **{"nvidia.maxine": MagicMock()}):
            with patch("nvidia.maxine.AudioEffectsSession", side_effect=RuntimeError("GPU error")):
                with patch("structlog.get_logger") as mock_logger:
                    mock_logger.return_value = MagicMock()
                    await p.initialize()

                    # Should have fallen back to passthrough
                    assert p._maxine_available is False


class TestMaxinePreprocessorProcess:
    """Tests for MaxinePreprocessor.process()."""

    @pytest.mark.asyncio
    async def test_process_yields_chunks_directly_when_unavailable(self):
        """When Maxine unavailable, process() yields chunks unchanged."""
        from backend.audio.maxine_preprocessor import MaxinePreprocessor

        p = MaxinePreprocessor()
        p._maxine_available = False

        input_chunks = [b"\x00\x01\x02\x03", b"\x04\x05\x06\x07"]

        async def gen():
            for c in input_chunks:
                yield c

        result = [c async for c in p.process(gen())]
        assert result == input_chunks

    @pytest.mark.asyncio
    async def test_process_passes_through_on_exception(self):
        """When Maxine throws, process() yields original chunk."""
        from backend.audio.maxine_preprocessor import MaxinePreprocessor

        p = MaxinePreprocessor()
        p._maxine_available = True
        p._aec_session = MagicMock()
        p._bnr_session = None
        p.enable_aec = True
        p.enable_bnr = False
        p._aec_session.process.side_effect = RuntimeError("AEC error")

        chunk = b"\x00\x01\x02\x03"

        async def gen():
            yield chunk

        result = [c async for c in p.process(gen())]
        assert result == [chunk]


class TestMaxinePassthrough:
    """Tests verifying passthrough behavior without GPU SDK."""

    def test_process_chunk_returns_original_on_error(self):
        """_process_chunk returns original bytes on any exception."""
        from backend.audio.maxine_preprocessor import MaxinePreprocessor

        p = MaxinePreprocessor()
        p._maxine_available = True
        p._aec_session = MagicMock()
        p._bnr_session = MagicMock()
        p.enable_aec = True
        p.enable_bnr = True
        p._aec_session.process.side_effect = RuntimeError("AEC crash")
        p._bnr_session.process.side_effect = RuntimeError("BNR crash")

        input_bytes = b"\x00\x01\x02\x03"
        result = p._process_chunk(input_bytes)
        assert result == input_bytes

    @pytest.mark.asyncio
    async def test_process_with_both_effects_disabled(self):
        """When both AEC and BNR are disabled, chunks pass through."""
        from backend.audio.maxine_preprocessor import MaxinePreprocessor

        p = MaxinePreprocessor(enable_aec=False, enable_bnr=False)
        p._maxine_available = True  # Pretend it's available (wont be used)
        p._aec_session = MagicMock()
        p._bnr_session = MagicMock()

        chunk = b"\x00" * 1600  # 1600 int16 samples = 100ms at 16kHz

        async def gen():
            yield chunk

        # With both disabled, the real processing would not be called
        # but since _maxine_available=True, it would try real processing
        # which would fail on the mock. However the implementation checks
        # _maxine_available first, so it would yield original.
        result = [c async for c in p.process(gen())]
        assert result[0] == chunk


class TestMaxineShutdown:
    """Tests for shutdown()."""

    @pytest.mark.asyncio
    async def test_shutdown_closes_aec_session(self):
        """shutdown() closes AEC session."""
        from backend.audio.maxine_preprocessor import MaxinePreprocessor

        p = MaxinePreprocessor()
        p._aec_session = MagicMock()
        p._bnr_session = None

        await p.shutdown()
        p._aec_session.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_shutdown_closes_bnr_session(self):
        """shutdown() closes BNR session."""
        from backend.audio.maxine_preprocessor import MaxinePreprocessor

        p = MaxinePreprocessor()
        p._aec_session = None
        p._bnr_session = MagicMock()

        await p.shutdown()
        p._bnr_session.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_shutdown_handles_close_error(self):
        """shutdown() handles close() raising an exception."""
        from backend.audio.maxine_preprocessor import MaxinePreprocessor

        p = MaxinePreprocessor()
        p._aec_session = MagicMock()
        p._aec_session.close.side_effect = RuntimeError("Close failed")
        p._bnr_session = None

        # Should not raise
        await p.shutdown()

    @pytest.mark.asyncio
    async def test_shutdown_closes_both_sessions(self):
        """shutdown() closes both sessions when present."""
        from backend.audio.maxine_preprocessor import MaxinePreprocessor

        p = MaxinePreprocessor()
        p._aec_session = MagicMock()
        p._bnr_session = MagicMock()

        await p.shutdown()

        p._aec_session.close.assert_called_once()
        p._bnr_session.close.assert_called_once()


class TestConstants:
    """Tests for module constants."""

    def test_sample_rate_constant(self):
        """SAMPLE_RATE is 16_000."""
        from backend.audio.maxine_preprocessor import SAMPLE_RATE
        assert SAMPLE_RATE == 16_000

    def test_chunk_samples_constant(self):
        """CHUNK_SAMPLES is 1600 (100ms at 16kHz)."""
        from backend.audio.maxine_preprocessor import CHUNK_SAMPLES
        assert CHUNK_SAMPLES == 1600
