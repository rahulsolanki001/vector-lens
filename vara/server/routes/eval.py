"""
Eval route.

POST /api/eval/run — load a dataset (CSV, JSON, or collection sample), start a
                     background eval job, return a job_id for the WebSocket to
                     stream results.
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from vara.adapters.base import VecDBAdapter
from vara.eval.loaders import CSVLoader, EvalDataset, JSONLoader
from vara.eval.runner import run_eval
from vara.eval.sampler import sample_collection
from vara.server.deps import get_adapters, get_eval_jobs, require_adapter

router = APIRouter(prefix="/eval", tags=["eval"])

# Strong references to background eval tasks so they aren't GC'd before completion
_eval_tasks: set[asyncio.Task[None]] = set()


class EvalRunRequest(BaseModel):
    # Dataset source — determines which other fields are required
    source: Literal["csv", "json", "collection"] = "csv"

    # File-based sources (csv / json)
    source_path: str | None = None

    # Collection-sample source
    n_samples: int = Field(default=50, ge=1, le=10_000)

    # Common
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
    Start an eval job.  Returns a job_id immediately.
    Connect to WS /ws/eval/{job_id} to stream EvalProgress events.
    """
    adapter = require_adapter(body.backend_name, adapters)

    if body.source in ("csv", "json"):
        if not body.source_path:
            raise HTTPException(
                status_code=422,
                detail=f"'source_path' is required when source='{body.source}'.",
            )
        try:
            if body.source == "csv":
                dataset = CSVLoader().load(body.source_path)
            else:
                dataset = JSONLoader().load(body.source_path)
        except (FileNotFoundError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    else:  # collection
        try:
            dataset = await sample_collection(adapter, body.collection, n_samples=body.n_samples)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    job_id = uuid.uuid4().hex
    queue: asyncio.Queue[Any] = asyncio.Queue()
    eval_jobs[job_id] = queue

    task = asyncio.create_task(_run_eval_task(dataset, body.collection, adapter, body, queue))
    _eval_tasks.add(task)
    task.add_done_callback(_eval_tasks.discard)

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
