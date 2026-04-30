"""
Query debugging API route placeholders.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/query", tags=["query"])


@router.post("/debug")
async def debug_query_route() -> dict[str, str]:
    """Run a debug query across one or more backends."""
    raise HTTPException(status_code=501, detail="Query debug API is planned for Phase 5.")


@router.post("/compare")
async def compare_backends_route() -> dict[str, str]:
    """Compare two backends for the same query."""
    raise HTTPException(status_code=501, detail="Query compare API is planned for Phase 5.")


@router.post("/diagnose")
async def diagnose_query_route() -> dict[str, str]:
    """Diagnose missing or low-ranked expected documents."""
    raise HTTPException(status_code=501, detail="Query diagnose API is planned for Phase 5.")


__all__ = ["router"]
