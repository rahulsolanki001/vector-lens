"""
Evaluation metric helpers.

Pure Python retrieval metrics used by the eval runner.

The first implementation assumes binary relevance: a retrieved document is
either relevant or not. Graded relevance can be layered in later without
changing callers that only have relevant ID sets.
"""

from __future__ import annotations

import math


def _validate_k(k: int) -> None:
    if k <= 0:
        raise ValueError(f"k must be positive, got {k}.")


def _dedupe_top_k(retrieved_ids: list[str], k: int) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []

    for doc_id in retrieved_ids:
        if doc_id in seen:
            continue
        seen.add(doc_id)
        deduped.append(doc_id)
        if len(deduped) == k:
            break

    return deduped


def _discount(rank: int) -> float:
    return 1.0 / math.log2(rank + 1)


def ndcg_at_k(retrieved_ids: list[str], relevant_ids: set[str], k: int) -> float:
    """
    Compute binary nDCG@k.

    Returns 0.0 when there are no relevant IDs, because there is no useful gain
    to normalize against.
    """
    _validate_k(k)
    if not relevant_ids:
        return 0.0

    dcg = 0.0
    for rank, doc_id in enumerate(_dedupe_top_k(retrieved_ids, k), start=1):
        if doc_id in relevant_ids:
            dcg += _discount(rank)

    ideal_hits = min(len(relevant_ids), k)
    idcg = sum(_discount(rank) for rank in range(1, ideal_hits + 1))
    if idcg == 0:
        return 0.0

    return dcg / idcg


def mrr_at_k(retrieved_ids: list[str], relevant_ids: set[str], k: int) -> float:
    """Compute reciprocal rank of the first relevant document within top k."""
    _validate_k(k)
    if not relevant_ids:
        return 0.0

    for rank, doc_id in enumerate(_dedupe_top_k(retrieved_ids, k), start=1):
        if doc_id in relevant_ids:
            return 1.0 / rank

    return 0.0


def recall_at_k(retrieved_ids: list[str], relevant_ids: set[str], k: int) -> float:
    """Compute recall@k for binary relevance labels."""
    _validate_k(k)
    if not relevant_ids:
        return 0.0

    retrieved_relevant = set(_dedupe_top_k(retrieved_ids, k)) & relevant_ids
    return len(retrieved_relevant) / len(relevant_ids)


def latency_percentiles(
    latencies_ms: list[float],
    percentiles: list[int],
) -> dict[int, float]:
    """
    Compute latency percentiles using linear interpolation.

    Percentiles must be integers from 0 to 100. Empty latency input returns an
    empty mapping, which keeps callers from mistaking missing samples for zero
    latency.
    """
    if not latencies_ms:
        return {}

    for percentile in percentiles:
        if not (0 <= percentile <= 100):
            raise ValueError(f"percentile must be between 0 and 100, got {percentile}.")

    sorted_latencies = sorted(latencies_ms)
    last_index = len(sorted_latencies) - 1
    results: dict[int, float] = {}

    for percentile in percentiles:
        position = (percentile / 100) * last_index
        lower_index = math.floor(position)
        upper_index = math.ceil(position)

        if lower_index == upper_index:
            results[percentile] = sorted_latencies[lower_index]
            continue

        lower_value = sorted_latencies[lower_index]
        upper_value = sorted_latencies[upper_index]
        weight = position - lower_index
        results[percentile] = lower_value + (upper_value - lower_value) * weight

    return results


__all__ = [
    "latency_percentiles",
    "mrr_at_k",
    "ndcg_at_k",
    "recall_at_k",
]
