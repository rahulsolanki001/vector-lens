"""
Projection job state.

Phase 4 will use this module to track asynchronous UMAP/t-SNE projection jobs
for the Vector Explorer.
"""

from __future__ import annotations

from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class ProjectionJobStatus(str, Enum):
    """Lifecycle states for a projection job."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETE = "complete"
    ERROR = "error"


class ProjectionPoint(BaseModel):
    """Projected point with optional metadata."""

    id: str
    x: float
    y: float
    z: float
    payload: dict[str, Any] = Field(default_factory=dict)


class ProjectionJob(BaseModel):
    """Stored projection job state."""

    id: str = Field(default_factory=lambda: uuid4().hex)
    status: ProjectionJobStatus = ProjectionJobStatus.PENDING
    points: list[ProjectionPoint] = Field(default_factory=list)
    error: str = ""


class ProjectionJobStore:
    """In-memory placeholder store for projection jobs."""

    def __init__(self) -> None:
        self._jobs: dict[str, ProjectionJob] = {}

    def create(self) -> ProjectionJob:
        job = ProjectionJob()
        self._jobs[job.id] = job
        return job

    def get(self, job_id: str) -> ProjectionJob:
        try:
            return self._jobs[job_id]
        except KeyError as exc:
            raise KeyError(f"No projection job named '{job_id}'.") from exc


__all__ = [
    "ProjectionJob",
    "ProjectionJobStatus",
    "ProjectionJobStore",
    "ProjectionPoint",
]
