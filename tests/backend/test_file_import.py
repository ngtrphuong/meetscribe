"""Comprehensive tests for audio file import.

Tests import_audio_file() and get_audio_duration() for all supported
formats, FFmpeg conversion, error handling, and supported extension
validation.
Run: pytest tests/backend/test_file_import.py -v
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from pathlib import Path
import tempfile


class TestSupportedExtensions:
    """Tests for SUPPORTED_EXTENSIONS constant."""

    def test_supported_extensions_contains_common_formats(self):
        """Verify all expected audio/video extensions are supported."""
        from backend.audio.file_import import SUPPORTED_EXTENSIONS

        expected = {
            ".wav", ".mp3", ".m4a", ".ogg", ".flac", ".aac",
            ".mp4", ".webm", ".mkv", ".avi", ".mov", ".ts",
        }
        assert expected.issubset(SUPPORTED_EXTENSIONS)


class TestImportAudioFileErrors:
    """Tests for import_audio_file() error handling."""

    @pytest.mark.asyncio
    async def test_file_not_found_error_message(self):
        """FileNotFoundError message contains the path."""
        from backend.audio.file_import import import_audio_file

        with pytest.raises(FileNotFoundError) as exc_info:
            await import_audio_file("/nonexistent/path/test.mp3")

        assert "Source file not found" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_unsupported_format_error_message(self, tmp_path):
        """ValueError message lists supported formats."""
        from backend.audio.file_import import import_audio_file

        fake = tmp_path / "document.pdf"
        fake.write_bytes(b"fake pdf content")

        with pytest.raises(ValueError) as exc_info:
            await import_audio_file(str(fake))

        assert "Unsupported format" in str(exc_info.value)
        assert ".pdf" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_raises_runtime_error_when_ffmpeg_missing(self, tmp_path):
        """RuntimeError when FFmpeg is not installed."""
        from backend.audio.file_import import import_audio_file

        fake = tmp_path / "test.wav"
        fake.write_bytes(b"RIFF")

        with patch("shutil.which", return_value=None):
            with pytest.raises(RuntimeError, match="FFmpeg is not installed"):
                await import_audio_file(str(fake))

    @pytest.mark.asyncio
    async def test_raises_runtime_error_on_ffmpeg_failure(self, tmp_path):
        """RuntimeError when FFmpeg conversion fails."""
        from backend.audio.file_import import import_audio_file

        fake = tmp_path / "test.mp3"
        fake.write_bytes(b"not a real mp3")

        with patch("shutil.which", return_value="ffmpeg"):
            mock_proc = AsyncMock()
            mock_proc.returncode = 1
            mock_proc.communicate = AsyncMock(return_value=(b"", b"ffmpeg error"))

            with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
                with pytest.raises(RuntimeError, match="FFmpeg conversion failed"):
                    await import_audio_file(str(fake))

    @pytest.mark.asyncio
    async def test_returns_path_to_converted_wav(self, tmp_path):
        """import_audio_file() returns path to converted WAV file on success."""
        from backend.audio.file_import import import_audio_file

        fake = tmp_path / "test.mp3"
        fake.write_bytes(b"fake mp3 content")

        output_wav = tmp_path / "output.wav"

        with patch("shutil.which", return_value="ffmpeg"):
            mock_proc = AsyncMock()
            mock_proc.returncode = 0
            mock_proc.communicate = AsyncMock(return_value=(b"", b""))

            with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
                result = await import_audio_file(str(fake), output_path=str(output_wav))

                assert result == str(output_wav)

    @pytest.mark.asyncio
    async def test_ffmpeg_command_uses_16khz_mono(self, tmp_path):
        """FFmpeg command is called with correct audio parameters."""
        from backend.audio.file_import import import_audio_file

        fake = tmp_path / "test.mp3"
        fake.write_bytes(b"fake mp3")

        output_wav = tmp_path / "output.wav"

        with patch("shutil.which", return_value="ffmpeg"):
            mock_proc = AsyncMock()
            mock_proc.returncode = 0
            mock_proc.communicate = AsyncMock(return_value=(b"", b""))

            captured_cmds = []

            async def capture_exec(*args, **kwargs):
                captured_cmds.append(list(args))
                return mock_proc

            with patch("asyncio.create_subprocess_exec", capture_exec):
                await import_audio_file(str(fake), output_path=str(output_wav))

                assert len(captured_cmds) == 1
                called_cmd = captured_cmds[0]
                assert "-ar" in called_cmd
                ar_idx = called_cmd.index("-ar")
                assert called_cmd[ar_idx + 1] == "16000"
                assert "-ac" in called_cmd
                ac_idx = called_cmd.index("-ac")
                assert called_cmd[ac_idx + 1] == "1"
                assert "-acodec" in called_cmd
                assert "-vn" in called_cmd

    @pytest.mark.asyncio
    async def test_ffmpeg_overwrites_existing_output(self, tmp_path):
        """FFmpeg is called with -y to overwrite output without prompting."""
        from backend.audio.file_import import import_audio_file

        fake = tmp_path / "test.mp3"
        fake.write_bytes(b"fake mp3")

        output_wav = tmp_path / "output.wav"

        with patch("shutil.which", return_value="ffmpeg"):
            mock_proc = AsyncMock()
            mock_proc.returncode = 0
            mock_proc.communicate = AsyncMock(return_value=(b"", b""))

            captured_cmds = []

            async def capture_exec(*args, **kwargs):
                captured_cmds.append(list(args))
                return mock_proc

            with patch("asyncio.create_subprocess_exec", capture_exec):
                await import_audio_file(str(fake), output_path=str(output_wav))

                assert len(captured_cmds) == 1
                called_cmd = captured_cmds[0]
                assert "-y" in called_cmd

    @pytest.mark.asyncio
    async def test_ffmpeg_no_video_flag(self, tmp_path):
        """FFmpeg is called with -vn to skip video stream."""
        from backend.audio.file_import import import_audio_file

        fake = tmp_path / "video.mp4"
        fake.write_bytes(b"fake video")

        with patch("shutil.which", return_value="ffmpeg"):
            mock_proc = AsyncMock()
            mock_proc.returncode = 0
            mock_proc.communicate = AsyncMock(return_value=(b"", b""))

            captured_cmds = []

            async def capture_exec(*args, **kwargs):
                captured_cmds.append(list(args))
                return mock_proc

            with patch("asyncio.create_subprocess_exec", capture_exec):
                await import_audio_file(str(fake))

                assert len(captured_cmds) == 1
                called_cmd = captured_cmds[0]
                assert "-vn" in called_cmd


class TestGetAudioDuration:
    """Tests for get_audio_duration()."""

    def test_returns_zero_for_nonexistent_file(self, tmp_path):
        """get_audio_duration() returns 0.0 for missing files."""
        from backend.audio.file_import import get_audio_duration

        result = get_audio_duration(str(tmp_path / "nonexistent.wav"))
        assert result == 0.0

    def test_returns_zero_for_invalid_wav(self, tmp_path):
        """get_audio_duration() returns 0.0 for invalid WAV files."""
        from backend.audio.file_import import get_audio_duration

        fake = tmp_path / "invalid.wav"
        fake.write_bytes(b"not a real wav file")

        result = get_audio_duration(str(fake))
        assert result == 0.0

    def test_returns_correct_duration_for_valid_wav(self, tmp_path):
        """get_audio_duration() calculates correct duration."""
        import wave
        from backend.audio.file_import import get_audio_duration

        wav_path = tmp_path / "valid.wav"
        with wave.open(str(wav_path), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(16000)
            # Write 48000 frames = 3 seconds at 16kHz
            wf.writeframes(b"\x00" * (48000 * 2))

        result = get_audio_duration(str(wav_path))
        assert result == 3.0

    def test_returns_correct_duration_different_sample_rates(self, tmp_path):
        """get_audio_duration() works with different sample rates."""
        import wave
        from backend.audio.file_import import get_audio_duration

        wav_path = tmp_path / "44khz.wav"
        with wave.open(str(wav_path), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(44100)
            # Write 44100 frames = 1 second at 44.1kHz
            wf.writeframes(b"\x00" * (44100 * 2))

        result = get_audio_duration(str(wav_path))
        assert result == 1.0
