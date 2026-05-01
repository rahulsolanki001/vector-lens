"""
Unit tests for the eval runner using a fake adapter.
"""

from __future__ import annotations

import time
from typing import Any

import pytest

from vara.adapters.base import (
    CollectionInfo,
    CollectionStats,
    HealthReport,
    QueryRequest,
    QueryResult,
    QueryHit,
    VecDBAdapter,
    VectorRecord,
)
from vara.eval.loaders import EvalDataset, EvalQuery
from vara.eval.runner import EvalProgress, run_eval


# ── Fake adapter ──────────────────────────────────────────────────────────────

class FakeAdapter(VecDBAdapter):
    """
    Returns a configurable list of hit IDs for every query.

    `hit_ids` is a list of document IDs returned (in order) for every query.
    `latency_ms` is fixed per call.
    """

    def __init__(self, hit_ids: list[str], latency_ms: float = 5.0) -> None:
        self._hit_ids = hit_ids
        self._latency_ms = latency_ms
        self.call_count = 0
        self.last_request: QueryRequest | None = None

    @property
    def name(self) -> str:
        return "fake"

    @property
    def backend_type(self) -> str:
        return "fake"

    async def connect(self) -> None:
        pass

    async def disconnect(self) -> None:
        pass

    async def list_collections(self) -> list[CollectionInfo]:
        return []

    async def collection_stats(self, collection: str) -> CollectionStats:
        raise NotImplementedError

    async def query(self, request: QueryRequest) -> QueryResult:
        self.call_count += 1
        self.last_request = request
        hits = [
            QueryHit(id=doc_id, score=1.0 - i * 0.1)
            for i, doc_id in enumerate(self._hit_ids)
        ]
        return QueryResult(
            hits=hits,
            total_hits=len(hits),
            backend_name="fake",
            collection=request.collection,
            latency_ms=self._latency_ms,
        )

    async def get_vectors(self, collection: str, ids: list[str]) -> list[VectorRecord]:
        return []

    async def health(self, collection: str) -> HealthReport:
        raise NotImplementedError


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_dataset(queries: list[EvalQuery], name: str = "test") -> EvalDataset:
    return EvalDataset(name=name, queries=queries)


def _make_query(
    qid: str,
    relevant_ids: set[str],
    dim: int = 4,
) -> EvalQuery:
    return EvalQuery(
        id=qid,
        text=f"query {qid}",
        vector=[1.0] * dim,
        relevant_ids=relevant_ids,
    )


async def _collect(gen) -> list[EvalProgress]:
    events: list[EvalProgress] = []
    async for event in gen:
        events.append(event)
    return events


# ── Tests ─────────────────────────────────────────────────────────────────────

@pytest.mark.unit
@pytest.mark.asyncio
async def test_emits_one_event_per_query() -> None:
    dataset = _make_dataset([_make_query("q1", {"doc1"}), _make_query("q2", {"doc2"})])
    adapter = FakeAdapter(hit_ids=["doc1", "doc2"])

    events = await _collect(run_eval(dataset, "col", adapter))

    assert len(events) == 2
    assert events[0].completed == 1
    assert events[0].total == 2
    assert events[1].completed == 2
    assert events[1].total == 2


@pytest.mark.unit
@pytest.mark.asyncio
async def test_final_event_contains_all_three_default_metrics() -> None:
    dataset = _make_dataset([_make_query("q1", {"doc1"})])
    adapter = FakeAdapter(hit_ids=["doc1"])

    events = await _collect(run_eval(dataset, "col", adapter))
    final = events[-1]

    assert "ndcg" in final.metrics
    assert "mrr" in final.metrics
    assert "recall" in final.metrics


@pytest.mark.unit
@pytest.mark.asyncio
async def test_perfect_retrieval_scores_one() -> None:
    dataset = _make_dataset([_make_query("q1", {"doc1", "doc2"})])
    adapter = FakeAdapter(hit_ids=["doc1", "doc2", "miss"])

    events = await _collect(run_eval(dataset, "col", adapter, k=2))
    final = events[-1]

    assert final.metrics["ndcg"] == pytest.approx(1.0)
    assert final.metrics["recall"] == pytest.approx(1.0)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_metrics_are_running_means() -> None:
    # q1: doc1 is hit (score=1.0), q2: doc3 is a miss (score=0.0)
    dataset = _make_dataset([
        _make_query("q1", {"doc1"}),
        _make_query("q2", {"doc3"}),
    ])
    adapter = FakeAdapter(hit_ids=["doc1", "doc2"])

    events = await _collect(run_eval(dataset, "col", adapter, metrics=["recall"]))

    # After q1: recall=1.0, mean=1.0
    assert events[0].metrics["recall"] == pytest.approx(1.0)
    # After q2: recall=0.0, mean=0.5
    assert events[1].metrics["recall"] == pytest.approx(0.5)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_latency_percentiles_reported() -> None:
    dataset = _make_dataset([_make_query("q1", {"doc1"}), _make_query("q2", {"doc2"})])
    adapter = FakeAdapter(hit_ids=["doc1"], latency_ms=10.0)

    events = await _collect(run_eval(dataset, "col", adapter))
    final = events[-1]

    assert "p50" in final.latency_ms
    assert "p95" in final.latency_ms
    assert "p99" in final.latency_ms
    assert final.latency_ms["p50"] == pytest.approx(10.0)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_subset_metrics_only() -> None:
    dataset = _make_dataset([_make_query("q1", {"doc1"})])
    adapter = FakeAdapter(hit_ids=["doc1"])

    events = await _collect(run_eval(dataset, "col", adapter, metrics=["mrr"]))
    final = events[-1]

    assert "mrr" in final.metrics
    assert "ndcg" not in final.metrics
    assert "recall" not in final.metrics


@pytest.mark.unit
@pytest.mark.asyncio
async def test_unknown_metric_raises() -> None:
    dataset = _make_dataset([_make_query("q1", {"doc1"})])
    adapter = FakeAdapter(hit_ids=["doc1"])

    with pytest.raises(ValueError, match="Unknown metric"):
        await _collect(run_eval(dataset, "col", adapter, metrics=["map"]))


@pytest.mark.unit
@pytest.mark.asyncio
async def test_dim_truncations_add_extra_metric_keys() -> None:
    dataset = _make_dataset([_make_query("q1", {"doc1"}, dim=8)])
    adapter = FakeAdapter(hit_ids=["doc1"])

    events = await _collect(
        run_eval(dataset, "col", adapter, metrics=["recall"], dim_truncations=[4])
    )
    final = events[-1]

    assert "recall" in final.metrics        # full vector
    assert "recall_dim4" in final.metrics   # truncated vector


@pytest.mark.unit
@pytest.mark.asyncio
async def test_dim_truncation_sends_shorter_vector() -> None:
    dataset = _make_dataset([_make_query("q1", {"doc1"}, dim=8)])
    adapter = FakeAdapter(hit_ids=["doc1"])

    # Capture the requests sent by tracking call count and last request
    requests_seen: list[QueryRequest] = []
    original_query = adapter.query

    async def capturing_query(request: QueryRequest) -> QueryResult:
        requests_seen.append(request)
        return await original_query(request)

    adapter.query = capturing_query  # type: ignore[method-assign]

    await _collect(run_eval(dataset, "col", adapter, dim_truncations=[4]))

    # Two calls: full vector (dim=8) and truncated (dim=4)
    assert len(requests_seen) == 2
    full_vec, trunc_vec = (r.vector for r in requests_seen)
    assert len(full_vec) == 8
    assert len(trunc_vec) == 4


@pytest.mark.unit
@pytest.mark.asyncio
async def test_latency_only_from_full_vector_pass() -> None:
    # With one dim_truncation, there are 2 backend calls per query.
    # Latency should only come from the full-vector call.
    dataset = _make_dataset([_make_query("q1", {"doc1"}, dim=4)])
    adapter = FakeAdapter(hit_ids=["doc1"], latency_ms=7.0)

    events = await _collect(
        run_eval(dataset, "col", adapter, dim_truncations=[2])
    )

    # Only 1 latency sample (from full-vector pass) → p50 = 7.0
    assert events[-1].latency_ms["p50"] == pytest.approx(7.0)
