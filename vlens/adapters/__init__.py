"""
vlens.adapters — DB adapter registry and factory.

Usage:
    from vlens.adapters import build_adapter
    adapter = build_adapter(config)
"""

from vlens.adapters.base import (
    AdapterConfig,
    CollectionInfo,
    CollectionStats,
    HealthReport,
    QueryRequest,
    QueryResult,
    VecDBAdapter,
    VectorRecord,
)

__all__ = [
    "AdapterConfig",
    "CollectionInfo",
    "CollectionStats",
    "HealthReport",
    "QueryRequest",
    "QueryResult",
    "VecDBAdapter",
    "VectorRecord",
    "build_adapter",
]


def build_adapter(config: AdapterConfig) -> VecDBAdapter:
    """
    Factory function — returns the correct adapter instance for a given config.

    Imports are intentionally lazy (inside the function) so that missing
    optional dependencies only raise at instantiation time, not at import time.
    This means `import vlens` works even if qdrant-client isn't installed.
    """
    match config.type:
        case "qdrant":
            from vlens.adapters.qdrant import QdrantAdapter

            return QdrantAdapter(config)  # type: ignore[arg-type]
        case "pinecone":
            from vlens.adapters.pinecone import PineconeAdapter

            return PineconeAdapter(config)  # type: ignore[arg-type]
        case "pgvector":
            from vlens.adapters.pgvector import PgvectorAdapter

            return PgvectorAdapter(config)  # type: ignore[arg-type]
        case "milvus":
            from vlens.adapters.milvus import MilvusAdapter

            return MilvusAdapter(config)  # type: ignore[arg-type]
        case "chroma":
            from vlens.adapters.chroma import ChromaAdapter

            return ChromaAdapter(config)  # type: ignore[arg-type]
        case _:
            raise ValueError(
                f"Unknown adapter type '{config.type}'. "
                f"Valid types: qdrant, pinecone, pgvector, milvus, chroma"
            )
