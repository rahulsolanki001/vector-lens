"""
Projection worker — fetches vectors, runs UMAP/t-SNE, streams point batches.

UMAP and scikit-learn are lazy-imported inside the sync helpers so the module
loads cleanly even when vara[projection] is not installed.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any

import numpy as np

from vara.adapters.base import VecDBAdapter
from vara.projection.jobs import ProjectionJobStore, ProjectionParams, ProjectionPoint


async def run_projection(
    adapter: VecDBAdapter,
    collection: str,
    ids: list[str],
    store: ProjectionJobStore,
    job_id: str,
    *,
    base_job_id: str | None = None,
) -> AsyncIterator[list[ProjectionPoint]]:
    """
    Run a projection job and stream projected point batches.

    Fetches vectors via the adapter, runs UMAP or t-SNE in a thread-pool
    executor (CPU-bound), then yields ProjectionPoint batches and updates
    the job store incrementally.

    Args:
        adapter: Connected adapter to fetch vectors from.
        collection: Collection / index name.
        ids: Vector IDs to project. Caller decides which subset to visualise.
        store: Job store to update with progress and results.
        job_id: ID of the PENDING job created by the caller.
        base_job_id: If provided and a fitted UMAP model is stored for that
            job, reuse it via transform() instead of fitting from scratch.
            Has no effect for t-SNE (which has no transform()).
    """
    params = store.get(job_id).params

    try:
        await store.mark_running(job_id, total=len(ids))

        records = await adapter.get_vectors(collection, ids)
        if not records:
            await store.mark_complete(job_id)
            return

        matrix = np.array([r.vector for r in records], dtype=np.float32)
        existing_model = store.get_model(base_job_id) if base_job_id else None

        loop = asyncio.get_running_loop()
        coords, fitted_model = await loop.run_in_executor(
            None, _project, matrix, params, existing_model
        )

        if fitted_model is not None:
            store.store_model(job_id, fitted_model)

        all_points = [
            ProjectionPoint(
                id=records[i].id,
                x=float(coords[i, 0]),
                y=float(coords[i, 1]),
                z=float(coords[i, 2]),
                payload=records[i].payload,
            )
            for i in range(len(records))
        ]

        for start in range(0, len(all_points), params.batch_size):
            batch = all_points[start : start + params.batch_size]
            await store.add_points(job_id, batch)
            yield batch

        await store.mark_complete(job_id)

    except Exception as exc:
        await store.mark_error(job_id, str(exc))
        raise


# ── Sync helpers (run inside executor) ───────────────────────────────────────

def _project(
    matrix: np.ndarray,
    params: ProjectionParams,
    existing_model: Any | None,
) -> tuple[np.ndarray, Any | None]:
    """Dispatch to the correct algorithm. Returns (coords_3d, fitted_model)."""
    if params.algorithm == "umap":
        return _run_umap(matrix, params, existing_model)
    if params.algorithm == "tsne":
        if existing_model is not None:
            raise ValueError(
                "Incremental projection is not supported for t-SNE. "
                "Use algorithm='umap' for incremental mode."
            )
        return _run_tsne(matrix, params)
    raise ValueError(
        f"Unknown projection algorithm '{params.algorithm}'. "
        "Supported: 'umap', 'tsne'."
    )


def _run_umap(
    matrix: np.ndarray,
    params: ProjectionParams,
    existing_model: Any | None,
) -> tuple[np.ndarray, Any]:
    try:
        import umap as umap_lib
    except ImportError as exc:
        raise ImportError(
            "umap-learn is required for UMAP projection.\n"
            "Install it with: pip install vara[projection]"
        ) from exc

    if existing_model is not None:
        # Incremental: no refit — just transform new vectors
        return existing_model.transform(matrix), existing_model

    model = umap_lib.UMAP(
        n_components=3,
        n_neighbors=params.n_neighbors,
        min_dist=params.min_dist,
        metric=params.metric,
    )
    return model.fit_transform(matrix), model


def _run_tsne(
    matrix: np.ndarray,
    params: ProjectionParams,
) -> tuple[np.ndarray, None]:
    try:
        from sklearn.manifold import TSNE
    except ImportError as exc:
        raise ImportError(
            "scikit-learn is required for t-SNE projection.\n"
            "Install it with: pip install vara[projection]"
        ) from exc

    model = TSNE(
        n_components=3,
        perplexity=params.perplexity,
        max_iter=params.n_iter,
    )
    return model.fit_transform(matrix), None


__all__ = ["run_projection"]
