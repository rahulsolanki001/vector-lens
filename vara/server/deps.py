"""
FastAPI dependency helpers shared across all route and WebSocket modules.

Import these into route files and use with Depends() to access adapters,
job stores, and config without touching request.app.state directly.
"""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import HTTPException, Request

from vara.adapters.base import VecDBAdapter
from vara.config.schema import VaraConfig
from vara.projection.jobs import ProjectionJobStore


def get_adapters(request: Request) -> dict[str, VecDBAdapter]:
    """Return the full adapter registry."""
    return request.app.state.adapters


def get_vara_config(request: Request) -> VaraConfig:
    """Return the loaded VaraConfig."""
    return request.app.state.config


def get_job_store(request: Request) -> ProjectionJobStore:
    """Return the projection job store."""
    return request.app.state.job_store


def get_eval_jobs(request: Request) -> dict[str, asyncio.Queue[Any]]:
    """Return the in-memory eval job queue registry."""
    return request.app.state.eval_jobs


def require_adapter(name: str, adapters: dict[str, VecDBAdapter]) -> VecDBAdapter:
    """Look up an adapter by name or raise 404."""
    if name not in adapters:
        available = sorted(adapters)
        raise HTTPException(
            status_code=404,
            detail=f"Backend '{name}' not found. Available: {available}.",
        )
    return adapters[name]


__all__ = [
    "get_adapters",
    "get_eval_jobs",
    "get_job_store",
    "get_vara_config",
    "require_adapter",
]
