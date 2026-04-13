"""ASR Engine factory and registry.

Creates ASR engines by name. All engines are lazily imported
to avoid loading heavy dependencies (torch, nemo, etc.) at startup.
"""

from __future__ import annotations

import importlib
from typing import Optional

from backend.asr.base import ASREngine

# Registry: engine name → (module_path, class_name)
ENGINE_REGISTRY: dict[str, tuple[str, str]] = {
    "parakeet-vi": ("backend.asr.parakeet_engine", "ParakeetVietnameseEngine"),
    "faster-whisper": ("backend.asr.faster_whisper_engine", "FasterWhisperEngine"),
    "vibevoice": ("backend.asr.vibevoice_engine", "VibeVoiceASREngine"),
    "phowhisper": ("backend.asr.phowhisper_engine", "PhoWhisperEngine"),
    "qwen3-asr": ("backend.asr.qwen3_asr_engine", "Qwen3ASREngine"),
    "gasr": ("backend.asr.gasr_engine", "GASREngine"),
    "cloud": ("backend.asr.cloud_engine", "CloudASREngine"),
    "whisper-asr-api": ("backend.asr.whisper_asr_client", "WhisperASRClient"),
    "whisperlivekit": ("backend.asr.whisperlivekit_engine", "WhisperLiveKitEngine"),
    "simulstreaming": ("backend.asr.simulstreaming_engine", "SimulStreamingEngine"),
    "gemma4": ("backend.asr.gemma4_engine", "Gemma4Engine"),
}


class ASREngineFactory:
    """Creates ASR engine instances by name."""

    _instances: dict[str, ASREngine] = {}

    @classmethod
    def create(cls, engine_name: str, config: Optional[dict] = None) -> ASREngine:
        """Create an ASR engine by name.

        Args:
            engine_name: Key from ENGINE_REGISTRY
            config: Engine-specific configuration dict

        Returns:
            Uninitialized ASREngine instance. Call await engine.initialize(config).

        Raises:
            ValueError: If engine_name is not in registry
            ImportError: If engine module/dependencies not installed
        """
        if engine_name not in ENGINE_REGISTRY:
            available = ", ".join(sorted(ENGINE_REGISTRY.keys()))
            raise ValueError(
                f"Unknown ASR engine '{engine_name}'. Available: {available}"
            )

        module_path, class_name = ENGINE_REGISTRY[engine_name]

        try:
            module = importlib.import_module(module_path)
            engine_class = getattr(module, class_name)
        except ImportError as e:
            raise ImportError(
                f"Cannot load engine '{engine_name}': {e}. "
                f"Install required dependencies. See README-DEVELOPER.md."
            ) from e

        return engine_class()

    @classmethod
    def list_engines(cls) -> list[dict]:
        """List all registered engines with availability status."""
        engines = []
        for name, (module_path, class_name) in ENGINE_REGISTRY.items():
            available = True
            error = None
            try:
                importlib.import_module(module_path)
            except ImportError as e:
                available = False
                error = str(e)

            engines.append({
                "name": name,
                "module": module_path,
                "class": class_name,
                "available": available,
                "error": error,
            })
        return engines
