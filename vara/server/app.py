"""
FastAPI application factory.

Responsibilities:
  - Load vara.yaml and connect all configured adapters at startup
  - Expose adapter registry and job stores on app.state for dependency injection
  - Register all REST routers and WebSocket routes
  - Serve the bundled React UI from vara/server/static/ (if present)
"""

from __future__ import annotations

import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from vara.adapters import build_adapter
from vara.config.loader import get_adapter_configs, load_config
from vara.projection.jobs import ProjectionJobStore
from vara.server.routes import collections, config, query
from vara.server.routes import eval as eval_routes
from vara.server.routes import projection as projection_routes
from vara.server.websocket.eval_stream import stream_eval_job
from vara.server.websocket.projection_stream import stream_projection_job

logger = logging.getLogger(__name__)

_STATIC_DIR = Path(__file__).parent / "static"

_DEFAULT_CORS_ORIGINS = [
    "http://localhost:7842",
    "http://127.0.0.1:7842",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]


def _make_lifespan(config_path: str) -> Any:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        cfg = load_config(config_path)
        adapter_configs = get_adapter_configs(cfg)

        adapters = {}
        for adapter_cfg in adapter_configs:
            adapter = build_adapter(adapter_cfg)
            try:
                await adapter.connect()
                adapters[adapter.name] = adapter
            except Exception as exc:
                logger.warning(
                    "Backend '%s' failed to connect at startup and will be skipped: %s",
                    adapter_cfg.name,
                    exc,
                )

        app.state.config = cfg
        app.state.adapters = adapters
        app.state.job_store = ProjectionJobStore()
        app.state.eval_jobs = {}

        yield

        for adapter in adapters.values():
            try:
                await adapter.disconnect()
            except Exception:
                pass

    return lifespan


def create_app(config_path: str | None = None) -> FastAPI:
    """
    Create and configure the Vara FastAPI application.

    Args:
        config_path: Path to vara.yaml. Reads VARA_CONFIG env var if not
            provided, falling back to "vara.yaml" in the current directory.
    """
    path = config_path or os.environ.get("VARA_CONFIG", "vara.yaml")

    # Load config early to pick up cors_origins for middleware setup.
    # Failures here are non-fatal — the lifespan will raise with a clear message.
    extra_origins: list[str] = []
    try:
        cfg = load_config(path)
        extra_origins = cfg.vara.cors_origins
    except Exception:
        pass

    app = FastAPI(
        title="Vara",
        description="Vector database debugger and visualizer.",
        version="0.1.0",
        lifespan=_make_lifespan(path),
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=_DEFAULT_CORS_ORIGINS + extra_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # REST routers
    app.include_router(config.router, prefix="/api")
    app.include_router(collections.router, prefix="/api")
    app.include_router(query.router, prefix="/api")
    app.include_router(eval_routes.router, prefix="/api")
    app.include_router(projection_routes.router, prefix="/api")

    # WebSocket routes — registered directly on app (not in APIRouter)
    @app.websocket("/ws/eval/{job_id}")
    async def ws_eval(websocket: WebSocket, job_id: str) -> None:
        await stream_eval_job(websocket, job_id, websocket.app.state)

    @app.websocket("/ws/projection")
    async def ws_projection(websocket: WebSocket) -> None:
        await stream_projection_job(websocket, websocket.app.state)

    # Bundled React UI — mounted last so /api/* takes priority
    if (_STATIC_DIR / "index.html").exists():
        app.mount("/", StaticFiles(directory=_STATIC_DIR, html=True), name="static")

    return app


# Module-level app instance for `uvicorn vara.server.app:app`
app = create_app()

__all__ = ["app", "create_app"]
