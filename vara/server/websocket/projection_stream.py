"""
WebSocket handler for streaming UMAP/t-SNE projection point batches.

WS /ws/projection

The client sends projection parameters as JSON in the first message,
then receives point batches until projection completes.

First client message (JSON):
    {
        "collection": "my_docs",
        "backend": "local-qdrant",
        "ids": ["id1", "id2", ...],
        "algorithm": "umap",       // optional, default "umap"
        "n_neighbors": 15,         // optional UMAP param
        "min_dist": 0.1,           // optional UMAP param
        "metric": "cosine",        // optional UMAP param
        "perplexity": 30.0,        // optional t-SNE param
        "n_iter": 1000,            // optional t-SNE param
        "batch_size": 250,         // optional streaming granularity
        "base_job_id": "..."       // optional: reuse fitted UMAP model
    }

Server messages (JSON):
    {"type": "started",  "job_id": "..."}
    {"type": "batch",    "points": [...], "projected": N, "total": N}
    {"type": "complete", "job_id": "..."}
    {"type": "error",    "error": "..."}
"""

from __future__ import annotations

from typing import Any

from fastapi import WebSocket, WebSocketDisconnect

from vara.projection.jobs import ProjectionJobStore, ProjectionParams
from vara.projection.worker import run_projection


async def stream_projection_job(
    websocket: WebSocket,
    state: Any,
) -> None:
    await websocket.accept()

    adapters: dict[str, Any] = state.adapters
    store: ProjectionJobStore = state.job_store

    try:
        raw = await websocket.receive_json()
    except (WebSocketDisconnect, Exception) as exc:
        await websocket.send_json({"type": "error", "error": f"Failed to read params: {exc}"})
        await websocket.close()
        return

    # Extract required fields
    collection = raw.get("collection", "")
    backend_name = raw.get("backend", "")
    ids: list[str] = raw.get("ids", [])
    base_job_id: str | None = raw.get("base_job_id")

    if not collection or not backend_name or not ids:
        await websocket.send_json(
            {
                "type": "error",
                "error": "Request must include 'collection', 'backend', and 'ids'.",
            }
        )
        await websocket.close()
        return

    if backend_name not in adapters:
        await websocket.send_json(
            {
                "type": "error",
                "error": f"Backend '{backend_name}' not found.",
            }
        )
        await websocket.close()
        return

    params = ProjectionParams(
        algorithm=raw.get("algorithm", "umap"),
        n_components=raw.get("n_components", 3),
        n_neighbors=raw.get("n_neighbors", 15),
        min_dist=raw.get("min_dist", 0.1),
        metric=raw.get("metric", "cosine"),
        perplexity=raw.get("perplexity", 30.0),
        n_iter=raw.get("n_iter", 1000),
        batch_size=raw.get("batch_size", 250),
    )

    job = await store.create(params)
    await websocket.send_json({"type": "started", "job_id": job.id})

    adapter = adapters[backend_name]

    try:
        async for batch in run_projection(
            adapter,
            collection,
            ids,
            store,
            job.id,
            base_job_id=base_job_id,
        ):
            current_job = store.get(job.id)
            await websocket.send_json(
                {
                    "type": "batch",
                    "points": [p.model_dump() for p in batch],
                    "projected": current_job.projected,
                    "total": current_job.total,
                }
            )

        await websocket.send_json({"type": "complete", "job_id": job.id})

    except WebSocketDisconnect:
        # Client left — mark job as error so the store reflects reality
        await store.mark_error(job.id, "Client disconnected during projection.")

    except Exception as exc:
        await websocket.send_json({"type": "error", "error": str(exc)})

    finally:
        await websocket.close()


__all__ = ["stream_projection_job"]
