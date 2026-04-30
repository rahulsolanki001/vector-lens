"""
Configuration API route placeholders.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

router = APIRouter(tags=["config"])


@router.get("/config")
async def get_config() -> dict[str, str]:
    """Return configured backend metadata."""
    raise HTTPException(status_code=501, detail="Config API is planned for Phase 5.")


__all__ = ["router"]
