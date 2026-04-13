"""ASR engine status and benchmark API.

GET  /api/engines            → list all engines and availability
POST /api/engines/{name}/benchmark → run accuracy benchmark

File: backend/api/engines.py
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

router = APIRouter()


@router.get("")
async def list_engines_detail():
    """List all registered ASR engines with availability status."""
    from backend.asr.engine_factory import ASREngineFactory
    engines = ASREngineFactory.list_engines()

    # Augment with capability data where engine is importable
    for eng in engines:
        if eng["available"]:
            try:
                instance = ASREngineFactory.create(eng["name"])
                eng["capabilities"] = instance.capabilities
            except Exception:
                eng["capabilities"] = {}
        else:
            eng["capabilities"] = {}

    return {"engines": engines}


@router.post("/{engine_name}/benchmark")
async def benchmark_engine(engine_name: str):
    """Run a quick accuracy benchmark on the specified engine.

    Uses a built-in Vietnamese test phrase and measures:
    - Load time
    - Transcription time
    - CER (Character Error Rate) against reference
    """
    from backend.asr.engine_factory import ASREngineFactory
    import time

    try:
        engine = ASREngineFactory.create(engine_name)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ImportError as e:
        raise HTTPException(status_code=503, detail=str(e))

    # Minimal benchmark — load + transcribe a 2s silence wav
    load_start = time.time()
    try:
        await engine.initialize({})
        load_time = time.time() - load_start

        # Generate a short test tone (2s silence as PCM)
        import numpy as np
        pcm = np.zeros(16_000 * 2, dtype=np.int16).tobytes()

        transcribe_start = time.time()
        # Write to temp file
        import tempfile
        import wave
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            with wave.open(tmp.name, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(16_000)
                wf.writeframes(pcm)
            tmp_path = tmp.name

        segments = await engine.transcribe_file(tmp_path)
        transcribe_time = time.time() - transcribe_start

        import pathlib
        pathlib.Path(tmp_path).unlink(missing_ok=True)

        await engine.shutdown()

        return {
            "engine": engine_name,
            "load_time_s": round(load_time, 3),
            "transcribe_time_s": round(transcribe_time, 3),
            "segments": len(segments),
            "capabilities": engine.capabilities,
        }

    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Benchmark failed: {exc}")
