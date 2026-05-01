"""
Evaluation runner.

Orchestrates dataset querying against a backend adapter, metric calculation,
and streaming progress events back to the caller.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from pydantic import BaseModel, Field

from vara.adapters.base import QueryRequest, QueryResult, VecDBAdapter
from vara.eval.loaders import EvalDataset, EvalQuery
from vara.eval.metrics import latency_percentiles, mrr_at_k, ndcg_at_k, recall_at_k

_SUPPORTED_METRICS = frozenset(["ndcg", "mrr", "recall"])
_DEFAULT_METRICS: list[str] = ["ndcg", "mrr", "recall"]


class EvalProgress(BaseModel):
    """One progress event emitted by a running evaluation job."""

    completed: int
    total: int
    # Running mean of each metric across completed queries.
    # Keys are metric names (e.g. "ndcg", "recall_dim128").
    metrics: dict[str, float] = Field(default_factory=dict)
    # Latency percentiles in ms across full-vector queries so far.
    # Keys are "p50", "p95", "p99".
    latency_ms: dict[str, float] = Field(default_factory=dict)


async def run_eval(
    dataset: EvalDataset,
    collection: str,
    backend: VecDBAdapter,
    *,
    k: int = 10,
    metrics: list[str] | None = None,
    dim_truncations: list[int] | None = None,
) -> AsyncIterator[EvalProgress]:
    """
    Run an evaluation job and stream EvalProgress events.

    One event is emitted after each query completes, with running-mean metrics
    accumulated over all completed queries. The final event reflects the full
    dataset.

    Args:
        dataset: Pre-loaded EvalDataset (use CSVLoader or another loader first).
        collection: Collection / index name to query on the backend.
        backend: Connected VecDBAdapter to query against.
        k: Cutoff depth for ranking metrics (ndcg@k, mrr@k, recall@k).
        metrics: Subset of ["ndcg", "mrr", "recall"]. Defaults to all three.
        dim_truncations: If provided, each query is also run with the vector
            truncated to each listed dimension. Metric keys for truncated runs
            are suffixed with the dimension (e.g. "ndcg_dim128").
    """
    active_metrics = _resolve_metrics(metrics)
    queries = dataset.queries
    total = len(queries)

    # key -> list of per-query scores (built up as queries complete)
    accumulators: dict[str, list[float]] = {m: [] for m in active_metrics}
    latencies: list[float] = []

    for completed, query in enumerate(queries, start=1):
        vector_configs = _build_vector_configs(query, dim_truncations)

        for suffix, vector in vector_configs:
            result = await _run_query(backend, collection, vector, k)
            retrieved_ids = [hit.id for hit in result.hits]

            for metric in active_metrics:
                key = metric + suffix
                if key not in accumulators:
                    accumulators[key] = []
                accumulators[key].append(
                    _compute_metric(metric, retrieved_ids, query.relevant_ids, k)
                )

            if not suffix:
                latencies.append(result.latency_ms)

        agg = {key: _mean(scores) for key, scores in accumulators.items() if scores}
        pct = latency_percentiles(latencies, [50, 95, 99]) if latencies else {}

        yield EvalProgress(
            completed=completed,
            total=total,
            metrics=agg,
            latency_ms={f"p{p}": v for p, v in pct.items()},
        )


def _resolve_metrics(metrics: list[str] | None) -> list[str]:
    requested = metrics if metrics is not None else _DEFAULT_METRICS
    unknown = [m for m in requested if m not in _SUPPORTED_METRICS]
    if unknown:
        raise ValueError(
            f"Unknown metric(s): {', '.join(unknown)}. "
            f"Supported: {', '.join(sorted(_SUPPORTED_METRICS))}."
        )
    return requested


def _build_vector_configs(
    query: EvalQuery,
    dim_truncations: list[int] | None,
) -> list[tuple[str, list[float]]]:
    configs: list[tuple[str, list[float]]] = [("", query.vector)]
    if dim_truncations:
        for dim in dim_truncations:
            configs.append((f"_dim{dim}", query.vector[:dim]))
    return configs


async def _run_query(
    backend: VecDBAdapter,
    collection: str,
    vector: list[float],
    top_k: int,
) -> QueryResult:
    return await backend.query(QueryRequest(collection=collection, vector=vector, top_k=top_k))


def _compute_metric(
    metric: str,
    retrieved_ids: list[str],
    relevant_ids: set[str],
    k: int,
) -> float:
    if metric == "ndcg":
        return ndcg_at_k(retrieved_ids, relevant_ids, k)
    if metric == "mrr":
        return mrr_at_k(retrieved_ids, relevant_ids, k)
    if metric == "recall":
        return recall_at_k(retrieved_ids, relevant_ids, k)
    raise ValueError(f"Unknown metric: {metric}")


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


__all__ = [
    "EvalProgress",
    "run_eval",
]
