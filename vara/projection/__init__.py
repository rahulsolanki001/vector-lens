"""
Vector projection service.

Phase 4 will expose background jobs and UMAP/t-SNE projection workers for the
Vector Explorer UI.
"""

from vara.projection.jobs import (
    ProjectionJob,
    ProjectionJobStatus,
    ProjectionJobStore,
    ProjectionParams,
    ProjectionPoint,
)
from vara.projection.worker import run_projection

__all__ = [
    "ProjectionJob",
    "ProjectionJobStatus",
    "ProjectionJobStore",
    "ProjectionParams",
    "ProjectionPoint",
    "run_projection",
]
