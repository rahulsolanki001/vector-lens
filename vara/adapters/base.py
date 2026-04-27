"""
vara.adapters.base — Abstract base class and shared data models for all DB adapters.

Every adapter (Qdrant, Pinecone, pgvector, Milvus) implements VecDBAdapter.
All data flowing between adapters and the core engine uses the Pydantic models
defined here — no adapter-specific types leak upward.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, Field


# ── Shared value types ────────────────────────────────────────────────────────

class AdapterType(str):
    QDRANT = "qdrant"
    PINECONE = "pinecone"
    PGVECTOR = "pgvector"
    MILVUS = "milvus"


# ── Config models (mirrors vara.yaml backend entries) ─────────────────────────

class AdapterConfig(BaseModel):
    """Base config — all adapters extend this."""
    name: str
    type: str


class QdrantConfig(AdapterConfig):
    type: str = "qdrant"
    host: str = "localhost"
    port: int = 6333
    api_key: str | None = None
    grpc_port: int = 6334
    prefer_grpc: bool = False
    default_collection: str = ""


class PineconeConfig(AdapterConfig):
    type: str = "pinecone"
    api_key: str
    index: str
    namespace: str = ""


class PgvectorConfig(AdapterConfig):
    type: str = "pgvector"
    dsn: str
    table: str
    vector_column: str = "embedding"
    id_column: str = "id"
    text_column: str = "text"


class MilvusConfig(AdapterConfig):
    type: str = "milvus"
    host: str = "localhost"
    port: int = 19530
    token: str | None = None
    default_collection: str = ""


# ── Collection / index info ───────────────────────────────────────────────────

class CollectionInfo(BaseModel):
    name: str
    vector_count: int
    dimension: int
    distance_metric: str          # cosine | dot | euclidean
    backend_name: str


class CollectionStats(BaseModel):
    """Detailed stats — superset of CollectionInfo, filled by health_check."""
    name: str
    backend_name: str
    vector_count: int
    dimension: int
    distance_metric: str
    disk_bytes: int | None = None
    ram_bytes: int | None = None
    segment_count: int | None = None
    index_type: str | None = None       # hnsw | ivf_flat | flat | etc.
    index_params: dict[str, Any] = Field(default_factory=dict)
    payload_indexes: list[str] = Field(default_factory=list)
    # Raw adapter-specific extras (Qdrant optimizer state, Milvus load state, etc.)
    raw: dict[str, Any] = Field(default_factory=dict)


# ── Query models ──────────────────────────────────────────────────────────────

class QueryRequest(BaseModel):
    collection: str
    vector: list[float]
    top_k: int = 10
    filters: dict[str, Any] | None = None    # Vara-canonical filter format
    with_payload: bool = True
    with_vectors: bool = False


class QueryHit(BaseModel):
    id: str
    score: float
    payload: dict[str, Any] = Field(default_factory=dict)
    vector: list[float] | None = None


class QueryResult(BaseModel):
    hits: list[QueryHit]
    total_hits: int
    backend_name: str
    collection: str
    latency_ms: float
    # The native query actually sent to this DB — shown in UI for filter translation
    native_query: dict[str, Any] = Field(default_factory=dict)


# ── Vector record (for fetching by ID) ───────────────────────────────────────

class VectorRecord(BaseModel):
    id: str
    vector: list[float]
    payload: dict[str, Any] = Field(default_factory=dict)
    backend_name: str


# ── Health report ─────────────────────────────────────────────────────────────

class HealthFinding(BaseModel):
    severity: str                  # error | warning | info
    code: str                      # machine-readable, e.g. "missing_payload_index"
    message: str                   # human-readable
    detail: str = ""               # extra context (raw metric that triggered this)
    recommendation: str = ""


class HealthReport(BaseModel):
    backend_name: str
    collection: str
    status: str                    # healthy | degraded | unhealthy
    findings: list[HealthFinding] = Field(default_factory=list)
    stats: CollectionStats | None = None
    latency_ms: float = 0.0


# ── Abstract adapter ──────────────────────────────────────────────────────────

class VecDBAdapter(ABC):
    """
    Abstract base class for all Vara vector DB adapters.

    Every method is async. Adapters must not import each other.
    Adapters must not leak native SDK types into return values —
    all returns must be the Pydantic models defined in this module.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """The user-defined name from vara.yaml (e.g. 'local-qdrant')."""
        pass

    @property
    @abstractmethod
    def backend_type(self) -> str:
        """The adapter type string (e.g. 'qdrant')."""
        pass

    @abstractmethod
    async def connect(self) -> None:
        """Establish connection. Called once at server startup."""
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """Clean up connection. Called on server shutdown."""
        pass

    @abstractmethod
    async def list_collections(self) -> list[CollectionInfo]:
        """Return all collections/indexes available on this backend."""
        pass

    @abstractmethod
    async def collection_stats(self, collection: str) -> CollectionStats:
        """Return detailed stats for a specific collection."""
        pass

    @abstractmethod
    async def query(self, request: QueryRequest) -> QueryResult:
        """
        Execute a vector similarity search.

        The adapter must populate native_query with the exact request
        it sent to the underlying DB, for display in the Query Debugger.
        """
        pass

    @abstractmethod
    async def get_vectors(self, collection: str, ids: list[str]) -> list[VectorRecord]:
        """Fetch specific vectors by ID — used by the Vector Explorer."""
        pass

    @abstractmethod
    async def health(self, collection: str) -> HealthReport:
        """
        Run adapter-specific health checks and return a structured report.

        Adapters should populate findings using the rule codes defined in
        vara.core.rules so findings are comparable across backends.
        """
        pass