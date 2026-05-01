"""
Disk-backed embedding cache for the eval harness.

Stores pre-computed query vectors in a numpy memmap so repeated eval runs
over the same dataset skip re-embedding. The cache is keyed by an arbitrary
string (typically query ID or a hash of the query text).
"""

from __future__ import annotations

import json
from pathlib import Path
from types import TracebackType

import numpy as np
import numpy.typing as npt


class EmbeddingCache:
    """
    Numpy memmap-backed embedding cache.

    Two files are written alongside the base path:
      - <path>.index.json  — JSON mapping string key → row index
      - <path>.vectors     — float32 memmap of shape (capacity, dimension)

    Usage::

        cache = EmbeddingCache("/tmp/my_eval")
        cache.open(dimension=768, capacity=5_000)
        cache.set("q1", my_vector)
        vec = cache.get("q1")
        cache.close()

    Or as a context manager::

        with EmbeddingCache("/tmp/my_eval") as cache:
            cache.open(dimension=768)
            ...
    """

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._index_path = self.path.with_suffix(".index.json")
        self._vector_path = self.path.with_suffix(".vectors")
        self._dimension: int = 0
        self._capacity: int = 0
        self._index: dict[str, int] = {}
        self._next_row: int = 0
        self._mmap: npt.NDArray[np.float32] | None = None

    def open(self, dimension: int, capacity: int = 10_000) -> None:
        """Open or create the cache. Must be called before get/set."""
        if self._index_path.exists():
            meta = json.loads(self._index_path.read_text())
            stored_dim = meta["dimension"]
            if stored_dim != dimension:
                raise ValueError(
                    f"Cache dimension mismatch: stored {stored_dim}, requested {dimension}."
                )
            self._dimension = stored_dim
            self._capacity = meta["capacity"]
            self._index = meta["index"]
            self._next_row = meta["next_row"]
        else:
            self._dimension = dimension
            self._capacity = capacity
            self._index = {}
            self._next_row = 0

        mode = "r+" if self._vector_path.exists() else "w+"
        self._mmap = np.memmap(
            self._vector_path,
            dtype=np.float32,
            mode=mode,
            shape=(self._capacity, self._dimension),
        )

    def close(self) -> None:
        """Flush memmap and persist the index to disk."""
        if self._mmap is not None:
            self._mmap.flush()
            del self._mmap
            self._mmap = None
        self._flush_index()

    def get(self, key: str) -> list[float] | None:
        """Return the cached vector for key, or None if not present."""
        self._require_open()
        row = self._index.get(key)
        if row is None:
            return None
        assert self._mmap is not None
        return self._mmap[row].tolist()

    def set(self, key: str, vector: list[float]) -> None:
        """Insert or overwrite a vector in the cache."""
        self._require_open()
        assert self._mmap is not None
        if len(vector) != self._dimension:
            raise ValueError(
                f"Vector length {len(vector)} does not match cache dimension {self._dimension}."
            )
        if key in self._index:
            row = self._index[key]
        else:
            if self._next_row >= self._capacity:
                raise OverflowError(
                    f"Cache is full ({self._capacity} entries). "
                    "Re-open with a larger capacity."
                )
            row = self._next_row
            self._index[key] = row
            self._next_row += 1
        self._mmap[row] = np.array(vector, dtype=np.float32)

    def __contains__(self, key: str) -> bool:
        return key in self._index

    def __len__(self) -> int:
        return self._next_row

    def __enter__(self) -> EmbeddingCache:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self.close()

    def _require_open(self) -> None:
        if self._mmap is None:
            raise RuntimeError("Cache is not open. Call open() first.")

    def _flush_index(self) -> None:
        meta = {
            "version": 1,
            "dimension": self._dimension,
            "capacity": self._capacity,
            "next_row": self._next_row,
            "index": self._index,
        }
        self._index_path.write_text(json.dumps(meta, indent=2))


__all__ = ["EmbeddingCache"]
