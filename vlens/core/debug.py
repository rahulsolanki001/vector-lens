"""
Query debugging helpers.

This module is the backend-agnostic query debugger. It fans a query out across
one or more adapters, preserves each adapter's native query payload, and builds
the alignment data needed by the UI to explain cross-backend differences.
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from typing import Any

from pydantic import BaseModel, Field

from vlens.adapters.base import QueryHit, QueryRequest, QueryResult, VecDBAdapter


class BackendQueryResult(BaseModel):
    """Successful query result from one backend."""

    backend_name: str
    backend_type: str
    result: QueryResult

    @property
    def hits(self) -> list[QueryHit]:
        """Convenience passthrough for retrieved hits."""
        return self.result.hits

    @property
    def native_query(self) -> dict[str, Any]:
        """The DB-native query payload produced by the adapter."""
        return self.result.native_query

    @property
    def latency_ms(self) -> float:
        """Adapter-reported query latency in milliseconds."""
        return self.result.latency_ms


class BackendQueryError(BaseModel):
    """A query failure from one backend."""

    backend_name: str
    backend_type: str
    error: str


class HitAlignment(BaseModel):
    """
    Cross-backend placement for one document ID.

    Ranks are one-based. Missing backends are listed explicitly so the UI can
    highlight documents that appear in one result set but not another.
    """

    id: str
    present_in: list[str] = Field(default_factory=list)
    missing_from: list[str] = Field(default_factory=list)
    ranks: dict[str, int] = Field(default_factory=dict)
    scores: dict[str, float] = Field(default_factory=dict)


class DebugQueryResult(BaseModel):
    """Result of running one query across one or more backends."""

    collection: str
    request: QueryRequest
    results: list[BackendQueryResult] = Field(default_factory=list)
    errors: list[BackendQueryError] = Field(default_factory=list)
    alignments: list[HitAlignment] = Field(default_factory=list)
    common_hit_ids: list[str] = Field(default_factory=list)
    unique_hit_ids_by_backend: dict[str, list[str]] = Field(default_factory=dict)
    missing_hit_ids_by_backend: dict[str, list[str]] = Field(default_factory=dict)


class BackendComparison(BaseModel):
    """Two-backend comparison for the side-by-side query debugger view."""

    backend_a: str
    backend_b: str
    debug: DebugQueryResult
    jaccard_similarity: float
    rank_spearman: float | None = None
    score_spearman: float | None = None


async def debug_query(
    query_vector: list[float],
    collection: str,
    backends: Sequence[VecDBAdapter],
    *,
    top_k: int = 10,
    filters: dict[str, Any] | None = None,
    with_payload: bool = True,
    with_vectors: bool = False,
) -> DebugQueryResult:
    """
    Run a vector search across one or more backends in parallel.

    Args:
        query_vector: Query embedding.
        collection: Collection/index name to query.
        backends: Connected vector DB adapters.
        top_k: Number of nearest neighbours to return per backend.
        filters: Optional Vector Lens canonical filter dictionary.
        with_payload: Include payload/metadata in hits.
        with_vectors: Include vectors in hits.

    Returns:
        A DebugQueryResult containing per-backend results, native queries,
        failures, and cross-backend hit alignment.
    """
    request = QueryRequest(
        collection=collection,
        vector=query_vector,
        top_k=top_k,
        filters=filters,
        with_payload=with_payload,
        with_vectors=with_vectors,
    )

    async def _run(adapter: VecDBAdapter) -> BackendQueryResult | BackendQueryError:
        try:
            result = await adapter.query(request)
        except Exception as exc:
            return BackendQueryError(
                backend_name=adapter.name,
                backend_type=adapter.backend_type,
                error=str(exc),
            )

        return BackendQueryResult(
            backend_name=adapter.name,
            backend_type=adapter.backend_type,
            result=result,
        )

    raw_results = await asyncio.gather(*(_run(adapter) for adapter in backends))

    results: list[BackendQueryResult] = []
    errors: list[BackendQueryError] = []
    for item in raw_results:
        if isinstance(item, BackendQueryError):
            errors.append(item)
        else:
            results.append(item)

    alignments = _align_hits(results)
    successful_backend_names = [result.backend_name for result in results]
    hit_ids_by_backend = _hit_ids_by_backend(results)
    all_hit_ids = set().union(*(set(ids) for ids in hit_ids_by_backend.values()))

    common_hit_ids = _common_hit_ids(hit_ids_by_backend)
    unique_hit_ids_by_backend = {
        backend_name: sorted(set(ids) - _other_backend_ids(hit_ids_by_backend, backend_name))
        for backend_name, ids in hit_ids_by_backend.items()
    }
    missing_hit_ids_by_backend = {
        backend_name: sorted(all_hit_ids - set(ids))
        for backend_name, ids in hit_ids_by_backend.items()
    }

    # Preserve successful backend keys even when there are no hits.
    for backend_name in successful_backend_names:
        unique_hit_ids_by_backend.setdefault(backend_name, [])
        missing_hit_ids_by_backend.setdefault(backend_name, [])

    return DebugQueryResult(
        collection=collection,
        request=request,
        results=results,
        errors=errors,
        alignments=alignments,
        common_hit_ids=common_hit_ids,
        unique_hit_ids_by_backend=unique_hit_ids_by_backend,
        missing_hit_ids_by_backend=missing_hit_ids_by_backend,
    )


async def compare_backends(
    query_vector: list[float],
    collection: str,
    backend_a: VecDBAdapter,
    backend_b: VecDBAdapter,
    *,
    top_k: int = 10,
    filters: dict[str, Any] | None = None,
    with_payload: bool = True,
    with_vectors: bool = False,
) -> BackendComparison:
    """
    Compare the same query across two backends.

    This is a focused wrapper around debug_query for the UI's side-by-side diff.
    It reports top-k set overlap plus rank and score correlations for shared
    document IDs.
    """
    debug = await debug_query(
        query_vector,
        collection,
        [backend_a, backend_b],
        top_k=top_k,
        filters=filters,
        with_payload=with_payload,
        with_vectors=with_vectors,
    )

    ids_a = _hit_ids(debug, backend_a.name)
    ids_b = _hit_ids(debug, backend_b.name)
    scores_a = _scores(debug, backend_a.name)
    scores_b = _scores(debug, backend_b.name)

    return BackendComparison(
        backend_a=backend_a.name,
        backend_b=backend_b.name,
        debug=debug,
        jaccard_similarity=_jaccard(ids_a, ids_b),
        rank_spearman=_spearman_ranks(ids_a, ids_b),
        score_spearman=_spearman_scores(scores_a, scores_b),
    )


def _hit_ids_by_backend(results: Sequence[BackendQueryResult]) -> dict[str, list[str]]:
    return {result.backend_name: [hit.id for hit in result.hits] for result in results}


def _common_hit_ids(hit_ids_by_backend: dict[str, list[str]]) -> list[str]:
    if not hit_ids_by_backend:
        return []

    id_sets = [set(ids) for ids in hit_ids_by_backend.values()]
    return sorted(set.intersection(*id_sets)) if id_sets else []


def _other_backend_ids(
    hit_ids_by_backend: dict[str, list[str]],
    backend_name: str,
) -> set[str]:
    other_ids: set[str] = set()
    for name, ids in hit_ids_by_backend.items():
        if name != backend_name:
            other_ids.update(ids)
    return other_ids


def _align_hits(results: Sequence[BackendQueryResult]) -> list[HitAlignment]:
    backend_names = [result.backend_name for result in results]
    by_id: dict[str, HitAlignment] = {}

    for result in results:
        for rank, hit in enumerate(result.hits, start=1):
            alignment = by_id.setdefault(hit.id, HitAlignment(id=hit.id))
            alignment.present_in.append(result.backend_name)
            alignment.ranks[result.backend_name] = rank
            alignment.scores[result.backend_name] = hit.score

    for alignment in by_id.values():
        alignment.present_in.sort()
        alignment.missing_from = sorted(set(backend_names) - set(alignment.present_in))

    return sorted(
        by_id.values(),
        key=lambda item: (min(item.ranks.values(), default=10**9), item.id),
    )


def _hit_ids(debug: DebugQueryResult, backend_name: str) -> list[str]:
    for result in debug.results:
        if result.backend_name == backend_name:
            return [hit.id for hit in result.hits]
    return []


def _scores(debug: DebugQueryResult, backend_name: str) -> dict[str, float]:
    for result in debug.results:
        if result.backend_name == backend_name:
            return {hit.id: hit.score for hit in result.hits}
    return {}


def _jaccard(ids_a: Sequence[str], ids_b: Sequence[str]) -> float:
    set_a = set(ids_a)
    set_b = set(ids_b)
    union = set_a | set_b
    if not union:
        return 1.0
    return round(len(set_a & set_b) / len(union), 6)


def _spearman_ranks(ids_a: Sequence[str], ids_b: Sequence[str]) -> float | None:
    ranks_a = {doc_id: rank for rank, doc_id in enumerate(ids_a, start=1)}
    ranks_b = {doc_id: rank for rank, doc_id in enumerate(ids_b, start=1)}
    common = sorted(set(ranks_a) & set(ranks_b))

    if len(common) < 2:
        return None

    values_a = [float(ranks_a[doc_id]) for doc_id in common]
    values_b = [float(ranks_b[doc_id]) for doc_id in common]
    return _pearson(values_a, values_b)


def _spearman_scores(
    scores_a: dict[str, float],
    scores_b: dict[str, float],
) -> float | None:
    common = sorted(set(scores_a) & set(scores_b))

    if len(common) < 2:
        return None

    ranked_a = _rank_values([scores_a[doc_id] for doc_id in common])
    ranked_b = _rank_values([scores_b[doc_id] for doc_id in common])
    return _pearson(ranked_a, ranked_b)


def _rank_values(values: Sequence[float]) -> list[float]:
    """
    Convert values to average ranks.

    Higher scores receive better ranks. Ties get the average of their occupied
    ranks, which keeps score correlation stable when many scores are equal.
    """
    indexed = sorted(enumerate(values), key=lambda item: item[1], reverse=True)
    ranks = [0.0] * len(values)
    i = 0

    while i < len(indexed):
        j = i + 1
        while j < len(indexed) and indexed[j][1] == indexed[i][1]:
            j += 1

        average_rank = (i + 1 + j) / 2
        for original_index, _ in indexed[i:j]:
            ranks[original_index] = average_rank
        i = j

    return ranks


def _pearson(values_a: Sequence[float], values_b: Sequence[float]) -> float | None:
    if len(values_a) != len(values_b) or len(values_a) < 2:
        return None

    mean_a = sum(values_a) / len(values_a)
    mean_b = sum(values_b) / len(values_b)
    centered_a = [value - mean_a for value in values_a]
    centered_b = [value - mean_b for value in values_b]

    numerator = sum(a * b for a, b in zip(centered_a, centered_b, strict=True))
    denom_a = sum(value * value for value in centered_a) ** 0.5
    denom_b = sum(value * value for value in centered_b) ** 0.5

    if denom_a == 0 or denom_b == 0:
        return None

    return float(round(numerator / (denom_a * denom_b), 6))


__all__ = [
    "BackendComparison",
    "BackendQueryError",
    "BackendQueryResult",
    "DebugQueryResult",
    "HitAlignment",
    "compare_backends",
    "debug_query",
]
