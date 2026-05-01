"""
Eval route.

POST /api/eval/run — load a CSV dataset, start a background eval job,
                     return a job_id for the WebSocket to stream results.
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from vara.adapters.base import VecDBAdapter
from vara.eval.loaders import CSVLoader, EvalDataset
from vara.eval.runner import EvalProgress, run_eval
from vara.server.deps import get_adapters, get_eval_jobs, require_adapter

router = APIRouter(prefix="/eval", tags=["eval"])


class EvalRunRequest(BaseModel):
    dataset_path: str
    collection: str
    backend_name: str
    k: int = Field(default=10, ge=1, le=1000)
    metrics: list[str] | None = None
    dim_truncations: list[int] | None = None


class EvalRunResponse(BaseModel):
    job_id: str
    total_queries: int


@router.post("/run", response_model=EvalRunResponse)
async def run_eval_route(
    body: EvalRunRequest,
    adapters: dict[str, VecDBAdapter] = Depends(get_adapters),
    eval_jobs: dict[str, asyncio.Queue[Any]] = Depends(get_eval_jobs),
) -> EvalRunResponse:
    """
    Start an eval job. Returns a job_id immediately.
    Connect to WS /ws/eval/{job_id} to stream EvalProgress events.
    """
    adapter = require_adapter(body.backend_name, adapters)

    try:
        dataset = CSVLoader().load(body.dataset_path)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    job_id = uuid.uuid4().hex
    queue: asyncio.Queue[Any] = asyncio.Queue()
    eval_jobs[job_id] = queue

    asyncio.create_task(
        _run_eval_task(dataset, body.collection, adapter, body, queue)
    )

    return EvalRunResponse(job_id=job_id, total_queries=dataset.query_count)


async def _run_eval_task(
    dataset: EvalDataset,
    collection: str,
    adapter: VecDBAdapter,
    body: EvalRunRequest,
    queue: asyncio.Queue[Any],
) -> None:
    try:
        async for progress in run_eval(
            dataset,
            collection,
            adapter,
            k=body.k,
            metrics=body.metrics,
            dim_truncations=body.dim_truncations,
        ):
            await queue.put(progress)
        await queue.put(None)  # sentinel: job complete
    except Exception as exc:
        await queue.put({"error": str(exc)})


__all__ = ["router"]
