"""
Projection job state and store for the Vector Explorer.

Jobs move through a one-way state machine:
    PENDING → RUNNING → COMPLETE
                      ↘ ERROR
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class ProjectionJobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETE = "complete"
    ERROR = "error"


class ProjectionParams(BaseModel):
    """Algorithm selection and tuning knobs for a projection run."""

    algorithm: str = "umap"  # "umap" | "tsne"
    n_components: int = 3  # 2 or 3 — output dimensionality

    # UMAP params
    n_neighbors: int = 15
    min_dist: float = 0.1
    metric: str = "cosine"

    # t-SNE params
    perplexity: float = 30.0
    n_iter: int = 1000

    # Streaming granularity — how many points per emitted batch
    batch_size: int = 250


class ProjectionPoint(BaseModel):
    """One projected point with its 3D coordinates and source payload."""

    id: str
    x: float
    y: float
    z: float
    payload: dict[str, Any] = Field(default_factory=dict)


class ProjectionJob(BaseModel):
    """Full state of one projection job."""

    id: str = Field(default_factory=lambda: uuid4().hex)
    status: ProjectionJobStatus = ProjectionJobStatus.PENDING
    params: ProjectionParams = Field(default_factory=ProjectionParams)

    # Progress counters
    total: int = 0  # total vectors to project
    projected: int = 0  # vectors projected so far

    # Accumulated output — full result once complete
    points: list[ProjectionPoint] = Field(default_factory=list)

    # Error detail (populated only on ERROR)
    error: str = ""

    # Timestamps (UTC ISO-8601)
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    started_at: str = ""
    finished_at: str = ""

    @property
    def progress(self) -> float:
        """Completion ratio [0.0, 1.0]."""
        return self.projected / self.total if self.total > 0 else 0.0


class ProjectionJobStore:
    """
    Thread-safe in-memory store for projection jobs.

    All mutating methods acquire an asyncio Lock so concurrent WebSocket
    handlers and the background worker never race on shared job state.

    Fitted UMAP models are held separately (they are not JSON-serialisable)
    so they survive job lookups without polluting the Pydantic model.
    """

    def __init__(self) -> None:
        self._jobs: dict[str, ProjectionJob] = {}
        self._models: dict[str, Any] = {}  # job_id → fitted UMAP model
        self._lock = asyncio.Lock()

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def create(self, params: ProjectionParams | None = None) -> ProjectionJob:
        """Create and register a new PENDING job."""
        job = ProjectionJob(params=params or ProjectionParams())
        async with self._lock:
            self._jobs[job.id] = job
        return job

    def get(self, job_id: str) -> ProjectionJob:
        """Return the job or raise KeyError."""
        try:
            return self._jobs[job_id]
        except KeyError as exc:
            raise KeyError(f"No projection job '{job_id}'.") from exc

    def all_jobs(self) -> list[ProjectionJob]:
        """Snapshot of all jobs (newest first by created_at)."""
        return sorted(self._jobs.values(), key=lambda j: j.created_at, reverse=True)

    # ── State transitions ─────────────────────────────────────────────────────

    async def mark_running(self, job_id: str, total: int) -> None:
        """Transition PENDING → RUNNING and record the vector count."""
        async with self._lock:
            job = self._jobs[job_id]
            job.status = ProjectionJobStatus.RUNNING
            job.total = total
            job.started_at = datetime.now(timezone.utc).isoformat()

    async def add_points(self, job_id: str, points: list[ProjectionPoint]) -> None:
        """Append a batch of projected points and advance the progress counter."""
        async with self._lock:
            job = self._jobs[job_id]
            job.points.extend(points)
            job.projected += len(points)

    async def mark_complete(self, job_id: str) -> None:
        """Transition RUNNING → COMPLETE."""
        async with self._lock:
            job = self._jobs[job_id]
            job.status = ProjectionJobStatus.COMPLETE
            job.finished_at = datetime.now(timezone.utc).isoformat()

    async def mark_error(self, job_id: str, message: str) -> None:
        """Transition any state → ERROR."""
        async with self._lock:
            job = self._jobs[job_id]
            job.status = ProjectionJobStatus.ERROR
            job.error = message
            job.finished_at = datetime.now(timezone.utc).isoformat()

    # ── Fitted model cache (incremental UMAP) ─────────────────────────────────

    def store_model(self, job_id: str, model: Any) -> None:
        """Cache the fitted UMAP model for later incremental transform() calls."""
        self._models[job_id] = model

    def get_model(self, job_id: str) -> Any | None:
        """Return the fitted model, or None if not yet stored."""
        return self._models.get(job_id)

    def has_model(self, job_id: str) -> bool:
        return job_id in self._models

    # ── Cleanup ───────────────────────────────────────────────────────────────

    async def delete(self, job_id: str) -> None:
        """Remove a job and its fitted model from the store."""
        async with self._lock:
            self._jobs.pop(job_id, None)
        self._models.pop(job_id, None)


__all__ = [
    "ProjectionJob",
    "ProjectionJobStatus",
    "ProjectionJobStore",
    "ProjectionParams",
    "ProjectionPoint",
]
