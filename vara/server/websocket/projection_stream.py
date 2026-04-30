"""
Projection WebSocket placeholder.
"""

from __future__ import annotations

from fastapi import WebSocket


async def stream_projection_job(websocket: WebSocket, job_id: str) -> None:
    """Stream projection coordinates for a job."""
    await websocket.close(
        code=1013,
        reason=f"Projection stream '{job_id}' is planned for Phase 5.",
    )


__all__ = ["stream_projection_job"]
