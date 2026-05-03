"""
WebSocket handler for streaming eval job progress.

WS /ws/eval/{job_id}

The client connects after receiving a job_id from POST /api/eval/run.
This handler reads EvalProgress events from the job's queue and forwards
them as JSON until the job completes or errors.
"""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect

from vara.eval.runner import EvalProgress


async def stream_eval_job(
    websocket: WebSocket,
    job_id: str,
    state: Any,
) -> None:
    await websocket.accept()

    eval_jobs: dict[str, asyncio.Queue[Any]] = state.eval_jobs
    queue = eval_jobs.get(job_id)

    if queue is None:
        await websocket.send_json({"error": f"Eval job '{job_id}' not found."})
        await websocket.close()
        return

    try:
        while True:
            item = await queue.get()

            if item is None:
                # Sentinel: job finished cleanly
                await websocket.send_json({"type": "complete"})
                break

            if isinstance(item, dict) and "error" in item:
                await websocket.send_json({"type": "error", "error": item["error"]})
                break

            if isinstance(item, EvalProgress):
                await websocket.send_json({"type": "progress", **item.model_dump()})

    except WebSocketDisconnect:
        pass
    finally:
        # Remove job from registry once the client has consumed it
        eval_jobs.pop(job_id, None)
        await websocket.close()


__all__ = ["stream_eval_job"]
