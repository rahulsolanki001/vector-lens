"""
Collection API route placeholders.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

router = APIRouter(tags=["collections"])


@router.get("/collections")
async def list_collections() -> dict[str, str]:
    """List collections across configured backends."""
    raise HTTPException(status_code=501, detail="Collection API is planned for Phase 5.")


@router.get("/collections/{collection}/health")
async def collection_health(collection: str) -> dict[str, str]:
    """Run health checks for a collection."""
    raise HTTPException(status_code=501, detail="Health API is planned for Phase 5.")


__all__ = ["router"]
