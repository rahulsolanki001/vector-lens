"""
GET /api/config — backend connection status.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from vlens.adapters.base import VecDBAdapter
from vlens.server.deps import get_adapters

router = APIRouter(tags=["config"])


class BackendStatus(BaseModel):
    name: str
    type: str


class ConfigResponse(BaseModel):
    version: str
    backends: list[BackendStatus]


@router.get("/config", response_model=ConfigResponse)
async def get_config(
    adapters: dict[str, VecDBAdapter] = Depends(get_adapters),
) -> ConfigResponse:
    """Return configured backends and their connection status."""
    return ConfigResponse(
        version="0.1.0",
        backends=[
            BackendStatus(name=name, type=adapter.backend_type)
            for name, adapter in adapters.items()
        ],
    )


__all__ = ["router"]
