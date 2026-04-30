"""
pgvector adapter placeholder.

The adapter registry can import this module today, but real pgvector support is
planned for a later Phase 1 expansion.
"""

from __future__ import annotations

from vara.adapters.base import (
    CollectionInfo,
    CollectionStats,
    HealthReport,
    PgvectorConfig,
    QueryRequest,
    QueryResult,
    VecDBAdapter,
    VectorRecord,
)


class PgvectorAdapter(VecDBAdapter):
    """Planned pgvector implementation of VecDBAdapter."""

    def __init__(self, config: PgvectorConfig) -> None:
        self._config = config

    @property
    def name(self) -> str:
        return self._config.name

    @property
    def backend_type(self) -> str:
        return "pgvector"

    async def connect(self) -> None:
        raise NotImplementedError("pgvector adapter is planned but not implemented yet.")

    async def disconnect(self) -> None:
        raise NotImplementedError("pgvector adapter is planned but not implemented yet.")

    async def list_collections(self) -> list[CollectionInfo]:
        raise NotImplementedError("pgvector adapter is planned but not implemented yet.")

    async def collection_stats(self, collection: str) -> CollectionStats:
        raise NotImplementedError("pgvector adapter is planned but not implemented yet.")

    async def query(self, request: QueryRequest) -> QueryResult:
        raise NotImplementedError("pgvector adapter is planned but not implemented yet.")

    async def get_vectors(self, collection: str, ids: list[str]) -> list[VectorRecord]:
        raise NotImplementedError("pgvector adapter is planned but not implemented yet.")

    async def health(self, collection: str) -> HealthReport:
        raise NotImplementedError("pgvector adapter is planned but not implemented yet.")


__all__ = ["PgvectorAdapter"]
