"""
Unit tests for retrieval evaluation metrics.
"""

from __future__ import annotations

import math

import pytest

from vara.eval.metrics import latency_percentiles, mrr_at_k, ndcg_at_k, recall_at_k


@pytest.mark.unit
def test_recall_at_k_counts_unique_relevant_hits() -> None:
    retrieved = ["doc1", "doc1", "doc2", "doc3"]
    relevant = {"doc1", "doc2", "doc4"}

    assert recall_at_k(retrieved, relevant, 3) == pytest.approx(2 / 3)


@pytest.mark.unit
def test_recall_at_k_returns_zero_when_no_relevant_ids() -> None:
    assert recall_at_k(["doc1"], set(), 10) == 0.0


@pytest.mark.unit
def test_mrr_at_k_uses_first_relevant_rank() -> None:
    retrieved = ["miss1", "miss2", "doc3", "doc4"]

    assert mrr_at_k(retrieved, {"doc3", "doc4"}, 10) == pytest.approx(1 / 3)


@pytest.mark.unit
def test_mrr_at_k_returns_zero_when_relevant_doc_is_beyond_k() -> None:
    assert mrr_at_k(["miss", "doc"], {"doc"}, 1) == 0.0


@pytest.mark.unit
def test_ndcg_at_k_is_one_for_perfect_ranking() -> None:
    retrieved = ["doc1", "doc2", "miss"]
    relevant = {"doc1", "doc2"}

    assert ndcg_at_k(retrieved, relevant, 3) == pytest.approx(1.0)


@pytest.mark.unit
def test_ndcg_at_k_discounts_late_relevant_hits() -> None:
    retrieved = ["miss", "doc1"]
    relevant = {"doc1"}

    expected = (1 / math.log2(3)) / 1.0
    assert ndcg_at_k(retrieved, relevant, 2) == pytest.approx(expected)


@pytest.mark.unit
def test_ndcg_at_k_returns_zero_when_no_relevant_ids() -> None:
    assert ndcg_at_k(["doc1"], set(), 10) == 0.0


@pytest.mark.unit
@pytest.mark.parametrize("metric", [recall_at_k, mrr_at_k, ndcg_at_k])
def test_rank_metrics_reject_non_positive_k(metric) -> None:
    with pytest.raises(ValueError, match="k must be positive"):
        metric(["doc1"], {"doc1"}, 0)


@pytest.mark.unit
def test_latency_percentiles_use_linear_interpolation() -> None:
    latencies = [40.0, 10.0, 20.0, 30.0]

    assert latency_percentiles(latencies, [0, 50, 95, 100]) == pytest.approx({
        0: 10.0,
        50: 25.0,
        95: 38.5,
        100: 40.0,
    })


@pytest.mark.unit
def test_latency_percentiles_return_empty_mapping_for_no_samples() -> None:
    assert latency_percentiles([], [50, 95]) == {}


@pytest.mark.unit
def test_latency_percentiles_reject_invalid_percentile() -> None:
    with pytest.raises(ValueError, match="between 0 and 100"):
        latency_percentiles([1.0, 2.0], [101])
