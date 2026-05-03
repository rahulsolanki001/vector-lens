"""
Projection REST routes.

POST /api/projection/{job_id}/cluster — run HDBSCAN on a completed projection job.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from vara.projection.cluster import run_hdbscan
from vara.projection.jobs import ProjectionJobStatus, ProjectionJobStore
from vara.server.deps import get_job_store

router = APIRouter(prefix="/projection", tags=["projection"])


class ClusterRequest(BaseModel):
    min_cluster_size: int = Field(default=5, ge=2)
    min_samples: int | None = None


class ClusterResponse(BaseModel):
    job_id: str
    labels: dict[str, int]  # point_id → cluster label; -1 = noise
    n_clusters: int
    noise_count: int


@router.post("/{job_id}/cluster", response_model=ClusterResponse)
async def cluster_projection(
    job_id: str,
    req: ClusterRequest,
    store: ProjectionJobStore = Depends(get_job_store),
) -> ClusterResponse:
    """Run HDBSCAN on the projected coordinates of a completed projection job."""
    try:
        job = store.get(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"No projection job '{job_id}'.") from exc

    if job.status != ProjectionJobStatus.COMPLETE:
        raise HTTPException(
            status_code=409,
            detail=f"Job '{job_id}' is not complete (status: {job.status.value}).",
        )

    if not job.points:
        raise HTTPException(status_code=422, detail="Job has no projected points.")

    try:
        labels = run_hdbscan(
            job.points,
            min_cluster_size=req.min_cluster_size,
            min_samples=req.min_samples,
        )
    except ImportError as exc:
        raise HTTPException(status_code=501, detail=str(exc)) from exc

    n_clusters = len({v for v in labels.values() if v != -1})
    noise_count = sum(1 for v in labels.values() if v == -1)

    return ClusterResponse(
        job_id=job_id,
        labels=labels,
        n_clusters=n_clusters,
        noise_count=noise_count,
    )


__all__ = ["router"]
