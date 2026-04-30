"""
Evaluation runner placeholder.

The runner will orchestrate dataset loading, backend queries, metric
calculation, dimension sweeps, and live progress streaming in Phase 3.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from pydantic import BaseModel, Field

from vara.adapters.base import VecDBAdapter


class EvalProgress(BaseModel):
    """One progress event emitted by a running evaluation job."""

    completed: int
    total: int
    metrics: dict[str, float] = Field(default_factory=dict)


async def run_eval(
    dataset: str,
    collection: str,
    backend: VecDBAdapter,
    *,
    metrics: list[str] | None = None,
    dim_truncations: list[int] | None = None,
) -> AsyncIterator[EvalProgress]:
    """Run an evaluation job and stream progress events."""
    raise NotImplementedError("Eval runner is planned for Phase 3.")
    yield  # pragma: no cover


__all__ = [
    "EvalProgress",
    "run_eval",
]
