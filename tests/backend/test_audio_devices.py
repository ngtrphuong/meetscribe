"""Comprehensive tests for audio device enumeration.

Tests list_devices, list_input_devices, list_loopback_devices, and helper
functions. Some tests are skipped when sounddevice is not available.
Run: pytest tests/backend/test_audio_devices.py -v
"""

import pytest
from unittest.mock import MagicMock, patch


class TestIsLoopbackDevice:
    """Tests for _is_loopback_device() helper."""

    def test_monitor_pattern(self):
        """PulseAudio/PipeWire monitor sources end with .monitor."""
        from backend.audio.devices import _is_loopback_device
        assert _is_loopback_device("alsa_output.pci-0000_00_1f.3.analog-stereo.monitor") is True

    def test_loopback_pattern(self):
        """Generic 'loopback' in name is detected."""
        from backend.audio.devices import _is_loopback_device
        assert _is_loopback_device("Built-in Loopback Device") is True

    def test_stereo_mix_pattern(self):
        """Windows legacy Stereo Mix is detected."""
        from backend.audio.devices import _is_loopback_device
        assert _is_loopback_device("Stereo Mix (Realtek High Definition Audio)") is True

    def test_blackhole_pattern(self):
        """macOS BlackHole virtual driver is detected."""
        from backend.audio.devices import _is_loopback_device
        assert _is_loopback_device("BlackHole 2ch") is True

    def test_wasapi_pattern(self):
        """Windows WASAPI loopback is detected."""
        from backend.audio.devices import _is_loopback_device
        assert _is_loopback_device("WASAPI Loopback (16 bit) Speakers (2- USB Audio Device)") is True

    def test_regular_microphone_not_loopback(self):
        """Regular microphone should NOT be detected as loopback."""
        from backend.audio.devices import _is_loopback_device
        assert _is_loopback_device("USB Microphone (Plantronics .Audio 626)") is False
        assert _is_loopback_device("Built-in Microphone") is False

    def test_case_insensitive(self):
        """Loopback detection is case-insensitive."""
        from backend.audio.devices import _is_loopback_device
        assert _is_loopback_device("LOOPBACK DEVICE") is True
        assert _is_loopback_device("alsa_output.pci-0000_00_1f.3.analog-stereo.monitor") is True
        assert _is_loopback_device("BLACKHOLE 2CH") is True


class TestListDevices:
    """Tests for list_devices() with mocked sounddevice."""

    def test_returns_list(self):
        """list_devices() returns a list."""
        mock_sd = MagicMock()
        mock_sd.query_devices.return_value = []
        mock_sd.default.device = (None, None)

        with patch.dict("sys.modules", sounddevice=mock_sd):
            # Need to re-import to pick up patched module
            import importlib
            import backend.audio.devices as dev_module
            importlib.reload(dev_module)

            result = dev_module.list_devices()
            assert isinstance(result, list)

    def test_empty_when_sounddevice_not_installed(self):
        """list_devices() returns empty list when sounddevice not installed."""
        with patch.dict("sys.modules", sounddevice=None):
            import importlib
            import backend.audio.devices as dev_module
            importlib.reload(dev_module)

            result = dev_module.list_devices()
            assert result == []

    def test_single_device_properties(self):
        """list_devices() returns correct device properties."""
        mock_dev = MagicMock()
        mock_dev.__getitem__ = lambda self, k: {
            "name": "Test Microphone",
            "hostapi": 0,
            "max_input_channels": 1,
            "max_output_channels": 0,
            "default_samplerate": 48000.0,
        }.get(k, 0)

        mock_hostapi = {"name": "MME"}
        mock_sd = MagicMock()
        mock_sd.query_devices.return_value = [mock_dev]
        mock_sd.default.device = (0, None)
        mock_sd.query_hostapis.return_value = mock_hostapi

        with patch.dict("sys.modules", sounddevice=mock_sd):
            import importlib
            import backend.audio.devices as dev_module
            importlib.reload(dev_module)

            devices = dev_module.list_devices()

            assert len(devices) == 1
            d = devices[0]
            assert d["id"] == 0
            assert d["name"] == "Test Microphone"
            assert d["hostapi"] == "MME"
            assert d["max_input_channels"] == 1
            assert d["max_output_channels"] == 0
            assert d["default_samplerate"] == 48000
            assert d["is_loopback"] is False
            assert d["is_default_input"] is True

    def test_loopback_device_detected(self):
        """Loopback device is correctly identified."""
        mock_dev = MagicMock()
        mock_dev.__getitem__ = lambda self, k: {
            "name": "alsa_output.monitor",
            "hostapi": 0,
            "max_input_channels": 0,
            "max_output_channels": 2,
            "default_samplerate": 44100.0,
        }.get(k, 0)

        mock_hostapi = {"name": "ALSA"}
        mock_sd = MagicMock()
        mock_sd.query_devices.return_value = [mock_dev]
        mock_sd.default.device = (None, None)
        mock_sd.query_hostapis.return_value = mock_hostapi

        with patch.dict("sys.modules", sounddevice=mock_sd):
            import importlib
            import backend.audio.devices as dev_module
            importlib.reload(dev_module)

            devices = dev_module.list_devices()

            assert len(devices) == 1
            assert devices[0]["is_loopback"] is True


class TestListInputDevices:
    """Tests for list_input_devices()."""

    def test_filters_to_input_only(self):
        """list_input_devices() returns only devices with max_input_channels > 0."""
        def make_dev(idx, inputs, outputs):
            m = MagicMock()
            m.__getitem__ = lambda self, k: {
                "name": f"Device {idx}", "hostapi": 0,
                "max_input_channels": inputs, "max_output_channels": outputs,
                "default_samplerate": 44100.0,
            }.get(k, 0)
            return m

        mock_sd = MagicMock()
        mock_sd.query_devices.return_value = [
            make_dev(0, inputs=1, outputs=0),  # Microphone
            make_dev(1, inputs=0, outputs=2),  # Speaker
            make_dev(2, inputs=2, outputs=2),  # Combined
        ]
        mock_sd.default.device = (0, None)
        mock_sd.query_hostapis.return_value = {"name": "Test"}

        with patch.dict("sys.modules", sounddevice=mock_sd):
            import importlib
            import backend.audio.devices as dev_module
            importlib.reload(dev_module)

            devices = dev_module.list_input_devices()

            assert len(devices) == 2
            assert all(d["max_input_channels"] > 0 for d in devices)


class TestListLoopbackDevices:
    """Tests for list_loopback_devices()."""

    def test_returns_loopback_devices(self):
        """list_loopback_devices() returns devices that are loopback."""
        def make_dev(idx, name, inputs, outputs):
            m = MagicMock()
            m.__getitem__ = lambda self, k: {
                "name": name, "hostapi": 0,
                "max_input_channels": inputs, "max_output_channels": outputs,
                "default_samplerate": 44100.0,
            }.get(k, 0)
            return m

        mock_sd = MagicMock()
        mock_sd.query_devices.return_value = [
            make_dev(0, "Microphone", inputs=1, outputs=0),
            make_dev(1, "Speaker", inputs=0, outputs=2),
            make_dev(2, "Monitor Source.monitor", inputs=0, outputs=2),  # .monitor pattern
        ]
        mock_sd.default.device = (None, None)
        mock_sd.query_hostapis.return_value = {"name": "Test"}

        with patch.dict("sys.modules", sounddevice=mock_sd):
            import importlib
            import backend.audio.devices as dev_module
            importlib.reload(dev_module)

            devices = dev_module.list_loopback_devices()

            assert len(devices) >= 1
            assert any(".monitor" in d["name"].lower() for d in devices)


class TestGetDefaultInputDevice:
    """Tests for get_default_input_device()."""

    def test_returns_default_input(self):
        """get_default_input_device() returns device where is_default_input=True."""
        def make_dev(idx, inputs, is_default):
            m = MagicMock()
            m.__getitem__ = lambda self, k: {
                "name": f"Device {idx}", "hostapi": 0,
                "max_input_channels": inputs, "max_output_channels": 0,
                "default_samplerate": 44100.0,
            }.get(k, 0)
            return m

        mock_sd = MagicMock()
        mock_sd.query_devices.return_value = [
            make_dev(0, inputs=1, is_default=False),
            make_dev(1, inputs=1, is_default=True),
        ]
        mock_sd.default.device = (1, None)
        mock_sd.query_hostapis.return_value = {"name": "Test"}

        with patch.dict("sys.modules", sounddevice=mock_sd):
            import importlib
            import backend.audio.devices as dev_module
            importlib.reload(dev_module)

            device = dev_module.get_default_input_device()

            assert device is not None
            assert device["id"] == 1
            assert device["is_default_input"] is True

    def test_returns_none_when_no_devices(self):
        """get_default_input_device() returns None when no input devices."""
        mock_sd = MagicMock()
        mock_sd.query_devices.return_value = []
        mock_sd.default.device = (None, None)
        mock_sd.query_hostapis.return_value = {"name": "Test"}

        with patch.dict("sys.modules", sounddevice=mock_sd):
            import importlib
            import backend.audio.devices as dev_module
            importlib.reload(dev_module)

            device = dev_module.get_default_input_device()

            assert device is None


class TestGetDeviceByName:
    """Tests for get_device_by_name()."""

    def test_partial_match_case_insensitive(self):
        """get_device_by_name() matches partial name case-insensitively."""
        def make_dev(idx, name):
            m = MagicMock()
            m.__getitem__ = lambda self, k: {
                "name": name, "hostapi": 0,
                "max_input_channels": 1, "max_output_channels": 0,
                "default_samplerate": 44100.0,
            }.get(k, 0)
            return m

        mock_sd = MagicMock()
        mock_sd.query_devices.return_value = [
            make_dev(0, "USB Microphone"),
            make_dev(1, "Built-in Microphone"),
        ]
        mock_sd.default.device = (0, None)
        mock_sd.query_hostapis.return_value = {"name": "Test"}

        with patch.dict("sys.modules", sounddevice=mock_sd):
            import importlib
            import backend.audio.devices as dev_module
            importlib.reload(dev_module)

            result = dev_module.get_device_by_name("usb")
            assert result is not None
            assert result["name"] == "USB Microphone"

            result = dev_module.get_device_by_name("BUILT-IN")
            assert result is not None
            assert result["name"] == "Built-in Microphone"

    def test_returns_none_when_not_found(self):
        """get_device_by_name() returns None for unknown name."""
        mock_sd = MagicMock()
        mock_sd.query_devices.return_value = []
        mock_sd.default.device = (None, None)
        mock_sd.query_hostapis.return_value = {"name": "Test"}

        with patch.dict("sys.modules", sounddevice=mock_sd):
            import importlib
            import backend.audio.devices as dev_module
            importlib.reload(dev_module)

            result = dev_module.get_device_by_name("nonexistent-device")
            assert result is None
