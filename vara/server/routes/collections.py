"""
Collection and health routes.

GET /api/collections                         — list all collections across backends
GET /api/collections/{backend}/{collection}/health — health check for one collection
"""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from vara.adapters.base import CollectionInfo, VecDBAdapter
from vara.core.health import HealthReport, health_check
from vara.server.deps import get_adapters, require_adapter

router = APIRouter(tags=["collections"])


class CollectionsResponse(BaseModel):
    collections: list[CollectionInfo]


@router.get("/collections", response_model=CollectionsResponse)
async def list_collections(
    adapters: dict[str, VecDBAdapter] = Depends(get_adapters),
) -> CollectionsResponse:
    """List all collections across every connected backend."""
    per_backend = await asyncio.gather(
        *(adapter.list_collections() for adapter in adapters.values()),
        return_exceptions=True,
    )
    collections: list[CollectionInfo] = []
    for result in per_backend:
        if isinstance(result, list):
            collections.extend(result)
    return CollectionsResponse(collections=collections)


@router.get(
    "/collections/{backend}/{collection}/health",
    response_model=HealthReport,
)
async def collection_health(
    backend: str,
    collection: str,
    adapters: dict[str, VecDBAdapter] = Depends(get_adapters),
) -> HealthReport:
    """Run health checks for one backend + collection pair."""
    adapter = require_adapter(backend, adapters)
    return await health_check(adapter, collection)


__all__ = ["router"]
