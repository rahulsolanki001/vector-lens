"""
Projection worker placeholder.

Phase 4 will fetch vectors through adapters, run UMAP/t-SNE, and stream point
batches over WebSocket.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from vara.adapters.base import VecDBAdapter
from vara.projection.jobs import ProjectionPoint


async def run_projection(
    adapter: VecDBAdapter,
    collection: str,
    ids: list[str],
) -> AsyncIterator[list[ProjectionPoint]]:
    """Run a projection job and stream projected point batches."""
    raise NotImplementedError("Projection worker is planned for Phase 4.")
    yield []  # pragma: no cover


__all__ = ["run_projection"]
