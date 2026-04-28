"""
vara.adapters.qdrant — Qdrant adapter.

Install: pip install vara[qdrant]

Supports:
  - Local Qdrant (host/port)
  - Qdrant Cloud (host + api_key)
  - gRPC transport (prefer_grpc=True)
  - Multi-tenant collections (payload filter per query)
"""

from __future__ import annotations

import time
from typing import Any

try:
    from qdrant_client import AsyncQdrantClient
    from qdrant_client.http import models as qmodels
except ImportError as e:
    raise ImportError(
        "qdrant-client is required for the Qdrant adapter.\n"
        "Install it with: pip install vara[qdrant]"
    ) from e

from vara.adapters.base import (
    CollectionInfo,
    CollectionStats,
    HealthFinding,
    HealthReport,
    QdrantConfig,
    QueryHit,
    QueryRequest,
    QueryResult,
    VecDBAdapter,
    VectorRecord,
)


# ── Distance metric mapping ───────────────────────────────────────────────────

_QDRANT_DISTANCE_MAP: dict[str, str] = {
    "Cosine": "cosine",
    "Dot": "dot",
    "Euclid": "euclidean",
    "Manhattan": "manhattan",
}

# ── Filter translation ────────────────────────────────────────────────────────

def _translate_filter(filters: dict[str, Any] | None) -> qmodels.Filter | None:
    """
    Translate Vara canonical filter format → Qdrant Filter model.

    Vara canonical format (mirrors a simple MongoDB-style DSL):

        # Exact match
        {"field": "value"}

        # Comparison
        {"field": {"$gt": 0.5}}
        {"field": {"$gte": 0.5, "$lte": 1.0}}

        # In list
        {"field": {"$in": ["a", "b"]}}

        # Logical
        {"$and": [{"field1": "val"}, {"field2": {"$gt": 0}}]}
        {"$or":  [{"field1": "val"}, {"field2": "val"}]}
        {"$not": {"field": "value"}}

    Returns None if filters is None or empty.
    """
    if not filters:
        return None

    must: list[qmodels.Condition] = []
    should: list[qmodels.Condition] = []
    must_not: list[qmodels.Condition] = []

    for key, value in filters.items():
        if key == "$and":
            # Recurse and collect into must
            for sub in value:
                sub_filter = _translate_filter(sub)
                if sub_filter:
                    must.append(sub_filter)  # type: ignore[arg-type]
        elif key == "$or":
            for sub in value:
                sub_filter = _translate_filter(sub)
                if sub_filter:
                    should.append(sub_filter)  # type: ignore[arg-type]
        elif key == "$not":
            sub_filter = _translate_filter(value)
            if sub_filter:
                must_not.append(sub_filter)  # type: ignore[arg-type]
        elif isinstance(value, dict):
            # Comparison operators on a field
            range_kwargs: dict[str, float] = {}
            in_values: list[Any] | None = None

            for op, operand in value.items():
                match op:
                    case "$gt":
                        range_kwargs["gt"] = operand
                    case "$gte":
                        range_kwargs["gte"] = operand
                    case "$lt":
                        range_kwargs["lt"] = operand
                    case "$lte":
                        range_kwargs["lte"] = operand
                    case "$in":
                        in_values = operand
                    case _:
                        raise ValueError(
                            f"Unsupported filter operator '{op}' on field '{key}'. "
                            f"Supported: $gt, $gte, $lt, $lte, $in"
                        )

            if in_values is not None:
                must.append(
                    qmodels.FieldCondition(
                        key=key,
                        match=qmodels.MatchAny(any=in_values),
                    )
                )
            elif range_kwargs:
                must.append(
                    qmodels.FieldCondition(
                        key=key,
                        range=qmodels.Range(**range_kwargs),
                    )
                )
        else:
            # Exact match
            must.append(
                qmodels.FieldCondition(
                    key=key,
                    match=qmodels.MatchValue(value=value),
                )
            )

    return qmodels.Filter(
        must=must or None,
        should=should or None,
        must_not=must_not or None,
    )


def _filter_to_dict(f: qmodels.Filter | None) -> dict[str, Any]:
    """Serialise a Qdrant Filter back to a plain dict for native_query display."""
    if f is None:
        return {}
    return f.model_dump(exclude_none=True)


# ── Adapter ───────────────────────────────────────────────────────────────────

class QdrantAdapter(VecDBAdapter):
    """
    Qdrant implementation of VecDBAdapter.

    Uses AsyncQdrantClient throughout — all public methods are coroutines.
    The native_query field of every QueryResult is populated with the exact
    Qdrant search parameters sent, so the UI can display filter translation.
    """

    def __init__(self, config: QdrantConfig) -> None:
        self._config = config
        self._client: AsyncQdrantClient | None = None

    # ── Identity ──────────────────────────────────────────────────────────────

    @property
    def name(self) -> str:
        return self._config.name

    @property
    def backend_type(self) -> str:
        return "qdrant"

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def connect(self) -> None:
        """
        Instantiate AsyncQdrantClient.

        Chooses transport based on config:
          - prefer_grpc=True  → gRPC on grpc_port
          - api_key set       → assume Qdrant Cloud (HTTPS)
          - otherwise         → plain HTTP
        """
        cfg = self._config

        if cfg.api_key:
            # Qdrant Cloud or secured local instance
            self._client = AsyncQdrantClient(
                host=cfg.host,
                port=cfg.port,
                api_key=cfg.api_key,
                prefer_grpc=cfg.prefer_grpc,
                grpc_port=cfg.grpc_port,
                https=True,
            )
        else:
            self._client = AsyncQdrantClient(
                host=cfg.host,
                port=cfg.port,
                prefer_grpc=cfg.prefer_grpc,
                grpc_port=cfg.grpc_port,
            )

    async def disconnect(self) -> None:
        """Close the async client gracefully."""
        if self._client is not None:
            await self._client.close()
            self._client = None

    # ── Internal helper ───────────────────────────────────────────────────────

    @property
    def _c(self) -> AsyncQdrantClient:
        """Return client, raising clearly if connect() was never called."""
        if self._client is None:
            raise RuntimeError(
                f"QdrantAdapter '{self.name}' is not connected. "
                "Call await adapter.connect() first."
            )
        return self._client

    # ── Collections ───────────────────────────────────────────────────────────

    async def list_collections(self) -> list[CollectionInfo]:
        """List all collections in this Qdrant instance."""
        response = await self._c.get_collections()
        result: list[CollectionInfo] = []

        for col in response.collections:
            try:
                info = await self._c.get_collection(col.name)
                config = info.config
                vec_config = config.params.vectors

                # vectors config can be a single VectorsConfig or a named dict
                if isinstance(vec_config, dict):
                    # Named vectors — take the first for dimension display
                    first = next(iter(vec_config.values()))
                    dimension = first.size
                    distance = _QDRANT_DISTANCE_MAP.get(
                        first.distance.value, first.distance.value
                    )
                else:
                    dimension = vec_config.size
                    distance = _QDRANT_DISTANCE_MAP.get(
                        vec_config.distance.value, vec_config.distance.value
                    )

                result.append(CollectionInfo(
                    name=col.name,
                    vector_count=info.vectors_count or 0,
                    dimension=dimension,
                    distance_metric=distance,
                    backend_name=self.name,
                ))
            except Exception:
                # Don't let a single bad collection break the whole list
                result.append(CollectionInfo(
                    name=col.name,
                    vector_count=0,
                    dimension=0,
                    distance_metric="unknown",
                    backend_name=self.name,
                ))

        return result

    async def collection_stats(self, collection: str) -> CollectionStats:
        """Return detailed stats for a collection — used by Index Health panel."""
        info = await self._c.get_collection(collection)
        config = info.config
        vec_config = config.params.vectors

        # Resolve dimension + distance
        if isinstance(vec_config, dict):
            first = next(iter(vec_config.values()))
            dimension = first.size
            distance = _QDRANT_DISTANCE_MAP.get(first.distance.value, first.distance.value)
        else:
            dimension = vec_config.size
            distance = _QDRANT_DISTANCE_MAP.get(
                vec_config.distance.value, vec_config.distance.value
            )

        # HNSW params
        hnsw = config.hnsw_config
        index_params: dict[str, Any] = {}
        if hnsw:
            index_params = {
                "m": hnsw.m,
                "ef_construct": hnsw.ef_construct,
                "full_scan_threshold": hnsw.full_scan_threshold,
                "max_indexing_threads": hnsw.max_indexing_threads,
            }

        # Payload field indexes
        payload_indexes: list[str] = []
        try:
            payload_schema = info.payload_schema or {}
            payload_indexes = list(payload_schema.keys())
        except Exception:
            pass

        # Segment info from optimizer status
        optimizer_status = info.optimizer_status
        segment_count: int | None = None
        try:
            # Qdrant doesn't expose segment count directly in get_collection —
            # use segments_count from the info object if available
            segment_count = getattr(info, "segments_count", None)
        except Exception:
            pass

        return CollectionStats(
            name=collection,
            backend_name=self.name,
            vector_count=info.vectors_count or 0,
            dimension=dimension,
            distance_metric=distance,
            disk_bytes=getattr(info, "disk_data_size", None),
            ram_bytes=getattr(info, "ram_data_size", None),
            segment_count=segment_count,
            index_type="hnsw",
            index_params=index_params,
            payload_indexes=payload_indexes,
            raw={
                "status": info.status.value if info.status else None,
                "optimizer_status": str(optimizer_status) if optimizer_status else None,
                "points_count": info.points_count,
                "indexed_vectors_count": info.indexed_vectors_count,
            },
        )

    # ── Query ─────────────────────────────────────────────────────────────────

    async def query(self, request: QueryRequest) -> QueryResult:
        """
        Execute a vector similarity search.

        Translates Vara canonical filters → Qdrant Filter, records the
        native query parameters for display in the Query Debugger UI.
        """
        qdrant_filter = _translate_filter(request.filters)

        # Build the native query dict for UI display (filter translation)
        native_query: dict[str, Any] = {
            "collection_name": request.collection,
            "query_vector": f"[{len(request.vector)}-dim vector]",
            "limit": request.top_k,
            "with_payload": request.with_payload,
            "with_vectors": request.with_vectors,
        }
        if qdrant_filter:
            native_query["filter"] = _filter_to_dict(qdrant_filter)

        t0 = time.perf_counter()

        results = await self._c.search(
            collection_name=request.collection,
            query_vector=request.vector,
            query_filter=qdrant_filter,
            limit=request.top_k,
            with_payload=request.with_payload,
            with_vectors=request.with_vectors,
        )

        latency_ms = (time.perf_counter() - t0) * 1000

        hits: list[QueryHit] = []
        for r in results:
            hits.append(QueryHit(
                id=str(r.id),
                score=r.score,
                payload=dict(r.payload) if r.payload else {},
                vector=list(r.vector) if r.vector else None,
            ))

        return QueryResult(
            hits=hits,
            total_hits=len(hits),
            backend_name=self.name,
            collection=request.collection,
            latency_ms=round(latency_ms, 3),
            native_query=native_query,
        )

    # ── Vector fetch ──────────────────────────────────────────────────────────

    async def get_vectors(self, collection: str, ids: list[str]) -> list[VectorRecord]:
        """
        Fetch vectors by ID — used by the Vector Explorer to load points
        into the UMAP projection.
        """
        # Qdrant IDs can be UUIDs (str) or unsigned ints
        # Try to cast to int; fall back to str UUID
        qdrant_ids: list[str | int] = []
        for raw_id in ids:
            try:
                qdrant_ids.append(int(raw_id))
            except ValueError:
                qdrant_ids.append(raw_id)

        results = await self._c.retrieve(
            collection_name=collection,
            ids=qdrant_ids,
            with_payload=True,
            with_vectors=True,
        )

        return [
            VectorRecord(
                id=str(r.id),
                vector=list(r.vector) if r.vector else [],  # type: ignore[arg-type]
                payload=dict(r.payload) if r.payload else {},
                backend_name=self.name,
            )
            for r in results
        ]

    # ── Health ────────────────────────────────────────────────────────────────

    async def health(self, collection: str) -> HealthReport:
        """
        Run Qdrant-specific health checks and return a structured report.

        Checks performed:
          1. Reachability (can we connect at all?)
          2. Collection status (green / yellow / grey)
          3. HNSW ef_construct vs collection size
          4. Missing payload indexes on likely-filtered fields
          5. Segment count (high segment count → compaction recommended)
          6. Indexed vectors vs total vectors (indexing lag)
        """
        findings: list[HealthFinding] = []
        t0 = time.perf_counter()

        # ── 1. Reachability ───────────────────────────────────────────────────
        try:
            await self._c.get_collections()
        except Exception as exc:
            return HealthReport(
                backend_name=self.name,
                collection=collection,
                status="unhealthy",
                findings=[HealthFinding(
                    severity="error",
                    code="unreachable",
                    message="Cannot connect to Qdrant instance.",
                    detail=str(exc),
                    recommendation=(
                        "Check that Qdrant is running and the host/port in vara.yaml are correct."
                    ),
                )],
                latency_ms=round((time.perf_counter() - t0) * 1000, 3),
            )

        # ── Fetch stats ───────────────────────────────────────────────────────
        try:
            stats = await self.collection_stats(collection)
        except Exception as exc:
            return HealthReport(
                backend_name=self.name,
                collection=collection,
                status="unhealthy",
                findings=[HealthFinding(
                    severity="error",
                    code="collection_not_found",
                    message=f"Collection '{collection}' not found or inaccessible.",
                    detail=str(exc),
                    recommendation="Check the collection name and Qdrant permissions.",
                )],
                latency_ms=round((time.perf_counter() - t0) * 1000, 3),
            )

        # ── 2. Collection status ──────────────────────────────────────────────
        raw_status = stats.raw.get("status")
        if raw_status == "grey":
            findings.append(HealthFinding(
                severity="warning",
                code="collection_status_grey",
                message="Collection is in 'grey' status — optimisation is pending.",
                detail=f"status={raw_status}",
                recommendation=(
                    "This is usually transient after bulk inserts. "
                    "If it persists, check Qdrant optimizer configuration."
                ),
            ))
        elif raw_status not in ("green", None):
            findings.append(HealthFinding(
                severity="error",
                code="collection_status_unhealthy",
                message=f"Collection status is '{raw_status}'.",
                detail=f"status={raw_status}",
                recommendation="Inspect Qdrant logs for optimizer errors.",
            ))

        # ── 3. HNSW ef_construct vs collection size ───────────────────────────
        ef_construct = stats.index_params.get("ef_construct", 0)
        vector_count = stats.vector_count

        if ef_construct and vector_count:
            # Rule: ef_construct < 64 is risky for recall at any scale;
            # ef_construct < 128 is marginal for collections > 100k vectors.
            if ef_construct < 64:
                findings.append(HealthFinding(
                    severity="error",
                    code="hnsw_ef_construct_too_low",
                    message=f"HNSW ef_construct={ef_construct} is very low — recall will be poor.",
                    detail=f"ef_construct={ef_construct}, vector_count={vector_count}",
                    recommendation=(
                        "Set ef_construct >= 100 for production workloads. "
                        "Recreate the collection or update the index config."
                    ),
                ))
            elif ef_construct < 128 and vector_count > 100_000:
                findings.append(HealthFinding(
                    severity="warning",
                    code="hnsw_ef_construct_marginal",
                    message=(
                        f"HNSW ef_construct={ef_construct} may be low "
                        f"for {vector_count:,} vectors."
                    ),
                    detail=f"ef_construct={ef_construct}, vector_count={vector_count}",
                    recommendation=(
                        "Consider ef_construct >= 128 for collections over 100k vectors "
                        "to maintain recall above 0.95."
                    ),
                ))

        # ── 4. HNSW m parameter ───────────────────────────────────────────────
        m = stats.index_params.get("m", 0)
        if m and m < 8:
            findings.append(HealthFinding(
                severity="warning",
                code="hnsw_m_too_low",
                message=f"HNSW m={m} is below the recommended minimum of 8.",
                detail=f"m={m}",
                recommendation=(
                    "m controls graph connectivity. Values below 8 reduce recall. "
                    "Default is 16; use 32–64 for high-recall requirements."
                ),
            ))

        # ── 5. Segment count ──────────────────────────────────────────────────
        if stats.segment_count is not None and stats.segment_count > 20:
            findings.append(HealthFinding(
                severity="warning",
                code="high_segment_count",
                message=f"High segment count ({stats.segment_count}) detected.",
                detail=f"segment_count={stats.segment_count}",
                recommendation=(
                    "Many small segments increase query latency. "
                    "Trigger compaction or review your optimizer settings "
                    "(indexing_threshold, memmap_threshold)."
                ),
            ))

        # ── 6. Indexing lag ───────────────────────────────────────────────────
        points_count = stats.raw.get("points_count") or 0
        indexed_count = stats.raw.get("indexed_vectors_count") or 0

        if points_count > 0 and indexed_count < points_count:
            lag_pct = ((points_count - indexed_count) / points_count) * 100
            if lag_pct > 10:
                findings.append(HealthFinding(
                    severity="warning",
                    code="indexing_lag",
                    message=(
                        f"{lag_pct:.1f}% of vectors are not yet indexed "
                        f"({points_count - indexed_count:,} unindexed)."
                    ),
                    detail=f"points_count={points_count}, indexed={indexed_count}",
                    recommendation=(
                        "Unindexed vectors fall back to brute-force search, "
                        "increasing latency. Wait for the optimizer to catch up, "
                        "or increase indexing_threshold in optimizer config."
                    ),
                ))

        # ── 7. Payload indexes ────────────────────────────────────────────────
        if not stats.payload_indexes:
            findings.append(HealthFinding(
                severity="info",
                code="no_payload_indexes",
                message="No payload field indexes found on this collection.",
                detail="payload_indexes=[]",
                recommendation=(
                    "If you filter by metadata fields (e.g. tenant_id, category), "
                    "create payload indexes for those fields to avoid full scans: "
                    "client.create_payload_index(collection, field_name, field_schema)"
                ),
            ))

        # ── Determine overall status ──────────────────────────────────────────
        severities = {f.severity for f in findings}
        if "error" in severities:
            status = "unhealthy"
        elif "warning" in severities:
            status = "degraded"
        else:
            status = "healthy"

        return HealthReport(
            backend_name=self.name,
            collection=collection,
            status=status,
            findings=findings,
            stats=stats,
            latency_ms=round((time.perf_counter() - t0) * 1000, 3),
        )