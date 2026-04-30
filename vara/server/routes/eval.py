"""
Evaluation API route placeholders.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/eval", tags=["eval"])


@router.post("/run")
async def run_eval_route() -> dict[str, str]:
    """Start an evaluation job."""
    raise HTTPException(status_code=501, detail="Eval API is planned for Phase 5.")


__all__ = ["router"]
