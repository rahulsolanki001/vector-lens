"""
Embedding cache placeholders for evaluation.

Phase 3 will add a numpy memmap-backed cache for large benchmark corpora.
"""

from __future__ import annotations

from pathlib import Path


class EmbeddingCache:
    """Planned disk-backed embedding cache."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def open(self) -> None:
        """Open or create the cache."""
        raise NotImplementedError("Embedding cache is planned for Phase 3.")

    def close(self) -> None:
        """Close cache resources."""
        raise NotImplementedError("Embedding cache is planned for Phase 3.")


__all__ = ["EmbeddingCache"]
