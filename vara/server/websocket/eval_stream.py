"""
Evaluation WebSocket placeholder.
"""

from __future__ import annotations

from fastapi import WebSocket


async def stream_eval_job(websocket: WebSocket, job_id: str) -> None:
    """Stream evaluation progress for a job."""
    await websocket.close(code=1013, reason=f"Eval stream '{job_id}' is planned for Phase 5.")


__all__ = ["stream_eval_job"]
