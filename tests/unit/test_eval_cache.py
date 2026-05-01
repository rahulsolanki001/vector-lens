"""
Unit tests for EmbeddingCache.
"""

from __future__ import annotations

import pytest

from vara.eval.cache import EmbeddingCache


@pytest.mark.unit
def test_set_and_get_round_trips(tmp_path) -> None:
    cache = EmbeddingCache(tmp_path / "cache")
    cache.open(dimension=4)
    cache.set("q1", [1.0, 2.0, 3.0, 4.0])
    result = cache.get("q1")
    cache.close()

    assert result == pytest.approx([1.0, 2.0, 3.0, 4.0])


@pytest.mark.unit
def test_get_returns_none_for_missing_key(tmp_path) -> None:
    cache = EmbeddingCache(tmp_path / "cache")
    cache.open(dimension=4)
    assert cache.get("missing") is None
    cache.close()


@pytest.mark.unit
def test_set_overwrites_existing_key(tmp_path) -> None:
    cache = EmbeddingCache(tmp_path / "cache")
    cache.open(dimension=2)
    cache.set("q1", [1.0, 2.0])
    cache.set("q1", [9.0, 8.0])
    result = cache.get("q1")
    cache.close()

    assert result == pytest.approx([9.0, 8.0])


@pytest.mark.unit
def test_len_tracks_unique_entries(tmp_path) -> None:
    cache = EmbeddingCache(tmp_path / "cache")
    cache.open(dimension=2)
    assert len(cache) == 0
    cache.set("a", [1.0, 0.0])
    cache.set("b", [0.0, 1.0])
    cache.set("a", [2.0, 0.0])  # overwrite — should not increment
    assert len(cache) == 2
    cache.close()


@pytest.mark.unit
def test_contains_operator(tmp_path) -> None:
    cache = EmbeddingCache(tmp_path / "cache")
    cache.open(dimension=2)
    cache.set("q1", [1.0, 1.0])
    assert "q1" in cache
    assert "q2" not in cache
    cache.close()


@pytest.mark.unit
def test_index_persists_across_reopen(tmp_path) -> None:
    cache_path = tmp_path / "cache"

    cache = EmbeddingCache(cache_path)
    cache.open(dimension=3)
    cache.set("q1", [1.0, 2.0, 3.0])
    cache.close()

    cache2 = EmbeddingCache(cache_path)
    cache2.open(dimension=3)
    result = cache2.get("q1")
    cache2.close()

    assert result == pytest.approx([1.0, 2.0, 3.0])


@pytest.mark.unit
def test_dimension_mismatch_on_reopen_raises(tmp_path) -> None:
    cache = EmbeddingCache(tmp_path / "cache")
    cache.open(dimension=4)
    cache.close()

    cache2 = EmbeddingCache(tmp_path / "cache")
    with pytest.raises(ValueError, match="dimension mismatch"):
        cache2.open(dimension=8)


@pytest.mark.unit
def test_wrong_vector_length_raises(tmp_path) -> None:
    cache = EmbeddingCache(tmp_path / "cache")
    cache.open(dimension=4)
    with pytest.raises(ValueError, match="does not match cache dimension"):
        cache.set("q1", [1.0, 2.0])
    cache.close()


@pytest.mark.unit
def test_overflow_raises(tmp_path) -> None:
    cache = EmbeddingCache(tmp_path / "cache")
    cache.open(dimension=2, capacity=2)
    cache.set("a", [1.0, 0.0])
    cache.set("b", [0.0, 1.0])
    with pytest.raises(OverflowError, match="Cache is full"):
        cache.set("c", [1.0, 1.0])
    cache.close()


@pytest.mark.unit
def test_get_without_open_raises(tmp_path) -> None:
    cache = EmbeddingCache(tmp_path / "cache")
    with pytest.raises(RuntimeError, match="not open"):
        cache.get("q1")


@pytest.mark.unit
def test_context_manager_closes_on_exit(tmp_path) -> None:
    cache_path = tmp_path / "cache"
    with EmbeddingCache(cache_path) as cache:
        cache.open(dimension=2)
        cache.set("q1", [1.0, 2.0])

    # Index file should have been flushed
    assert cache_path.with_suffix(".index.json").exists()
