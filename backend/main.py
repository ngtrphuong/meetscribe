"""MeetScribe Backend — FastAPI entry point.

Start with: uvicorn backend.main:app --reload --port 9876
"""

from __future__ import annotations

import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

try:
    from fastapi.responses import ORJSONResponse
except ImportError:
    from fastapi.responses import JSONResponse as ORJSONResponse

from backend.config import settings

# Use uvloop on Linux/macOS for faster event loop
if sys.platform != "win32":
    try:
        import uvloop
        uvloop.install()
    except ImportError:
        pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle."""
    import structlog
    logger = structlog.get_logger()

    # Ensure data directories exist
    settings.ensure_dirs()

    # Initialise database schema
    from backend.database import init_db
    await init_db()

    logger.info("MeetScribe starting", port=settings.port, env=settings.env)

    yield

    logger.info("MeetScribe shutting down")


app = FastAPI(
    title="MeetScribe API",
    description="Vietnamese-first AI Meeting Intelligence Platform",
    version="0.2.0",
    default_response_class=ORJSONResponse,
    lifespan=lifespan,
)

# CORS — allow Angular dev server and Electron
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:4200",   # Angular dev server
        "http://localhost:9876",   # Self
        "http://127.0.0.1:4200",
        "http://127.0.0.1:9876",
        "app://.",                 # Electron
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/health")
async def health():
    """Health check endpoint."""
    import torch
    gpu_available = torch.cuda.is_available() if "torch" in sys.modules else False
    gpu_name = torch.cuda.get_device_name(0) if gpu_available else None
    gpu_vram_mb = (
        torch.cuda.get_device_properties(0).total_memory // (1024 * 1024)
        if gpu_available
        else 0
    )

    from backend.asr.engine_factory import ASREngineFactory
    engines = ASREngineFactory.list_engines()

    return {
        "status": "ok",
        "version": "0.2.0",
        "gpu": {
            "available": gpu_available,
            "name": gpu_name,
            "vram_mb": gpu_vram_mb,
        },
        "engines": engines,
        "default_language": settings.default_language,
        "llm_provider": settings.llm_provider,
    }


# ── Register routers (imported lazily to avoid circular imports) ──────────────
def _register_routers() -> None:
    from backend.api import (
        recording,
        meetings,
        search as search_api,
        settings as settings_api,
        engines as engines_api,
        compliance,
        websocket as ws_api,
    )
    app.include_router(recording.router,    prefix="/api/recording",   tags=["recording"])
    app.include_router(meetings.router,     prefix="/api/meetings",    tags=["meetings"])
    app.include_router(search_api.router,   prefix="/api/search",      tags=["search"])
    app.include_router(settings_api.router, prefix="/api/settings",    tags=["settings"])
    app.include_router(engines_api.router,  prefix="/api/engines",     tags=["engines"])
    app.include_router(compliance.router,   prefix="/api/compliance",  tags=["compliance"])
    app.include_router(ws_api.router,                                  tags=["websocket"])


_register_routers()

# Serve Angular production build — mounted LAST so /api/* routes take priority
_frontend_dist = Path(__file__).parent.parent / "frontend" / "dist" / "meetscribe-web" / "browser"
if _frontend_dist.exists():
    app.mount("/", StaticFiles(directory=str(_frontend_dist), html=True), name="frontend")
