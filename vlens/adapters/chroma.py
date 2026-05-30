"""
vlens.adapters.chroma — ChromaDB adapter.

Install: pip install vector-lens[chroma]

Supports:
  - ChromaDB HTTP server (mode: http)
  - Local persistent Chroma (mode: persistent, path: /some/dir)
  - In-memory ephemeral Chroma (mode: ephemeral)
  - Multi-tenant scoping via tenant + database params
"""

from __future__ import annotations

import asyncio
import functools
import time
from typing import Any

try:
    import chromadb
except ImportError as exc:
    raise ImportError(
        "chromadb is required for the Chroma adapter.\n"
        "Install it with: pip install vector-lens[chroma]"
    ) from exc

from vlens.adapters.base import (
    ChromaConfig,
    CollectionInfo,
    CollectionStats,
    HealthFinding,
    HealthReport,
    QueryHit,
    QueryRequest,
    QueryResult,
    VecDBAdapter,
    VectorRecord,
)

# ── Distance metric mapping ───────────────────────────────────────────────────

_METRIC_MAP: dict[str, str] = {
    "l2": "euclidean",
    "cosine": "cosine",
    "ip": "dot",
}


def _distance_to_score(distance: float, space: str) -> float:
    """
    Convert Chroma's "lower is better" distances to similarity scores.

    Chroma returns distances, not similarities:
      cosine: distance = 1 - cosine_similarity  → score = 1 - distance
      ip:     distance = -(inner_product)        → score = -distance
      l2:     raw L2²                            → score = 1 / (1 + distance)
    """
    if space == "cosine":
        return 1.0 - distance
    if space == "ip":
        return -distance
    return 1.0 / (1.0 + distance)


# ── Filter translation ────────────────────────────────────────────────────────


def _translate_filter(filters: dict[str, Any]) -> dict[str, Any]:
    """
    Translate Vector Lens canonical filter dict → Chroma where clause.

    Chroma uses a MongoDB-style where syntax; the main differences from
    the VL canonical format are:
      - VL bare equality  {"field": "val"} → Chroma {"field": {"$eq": "val"}}
      - VL $not is not supported by Chroma at the top level — raises ValueError
      - All other operators ($gt, $gte, $lt, $lte, $ne, $eq, $in, $nin) pass through
    """
    result: dict[str, Any] = {}

    for key, value in filters.items():
        if key == "$and":
            result["$and"] = [_translate_filter(sub) for sub in value]
        elif key == "$or":
            result["$or"] = [_translate_filter(sub) for sub in value]
        elif key == "$not":
            raise ValueError(
                "Chroma does not support a top-level $not filter. "
                "Use $and/$or with negated conditions instead."
            )
        elif isinstance(value, dict):
            valid_ops = {"$gt", "$gte", "$lt", "$lte", "$ne", "$eq", "$in", "$nin"}
            for op in value:
                if op not in valid_ops:
                    raise ValueError(
                        f"Unsupported filter operator '{op}' on field '{key}' for Chroma. "
                        f"Supported: {sorted(valid_ops)}"
                    )
            result[key] = value
        else:
            result[key] = {"$eq": value}

    return result


# ── Adapter ───────────────────────────────────────────────────────────────────


class ChromaAdapter(VecDBAdapter):
    """
    ChromaDB implementation of VecDBAdapter.

    HTTP mode uses chromadb.AsyncHttpClient for non-blocking I/O.
    Persistent and ephemeral modes wrap the sync client in a thread-pool
    executor to avoid blocking the FastAPI event loop.
    """

    def __init__(self, config: ChromaConfig) -> None:
        self._config = config
        self._client: Any = None
        self._is_async = False

    # ── Identity ──────────────────────────────────────────────────────────────

    @property
    def name(self) -> str:
        return self._config.name

    @property
    def backend_type(self) -> str:
        return "chroma"

    # ── Executor helper ───────────────────────────────────────────────────────

    async def _run(self, fn: Any, *args: Any, **kwargs: Any) -> Any:
        """Run a synchronous callable in the default thread-pool executor."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, functools.partial(fn, *args, **kwargs))

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def connect(self) -> None:
        cfg = self._config

        if cfg.mode == "http":
            self._client = await chromadb.AsyncHttpClient(
                host=cfg.host,
                port=cfg.port,
                ssl=cfg.ssl,
                headers=cfg.headers or {},
                tenant=cfg.tenant,
                database=cfg.database,
            )
            self._is_async = True
        elif cfg.mode == "persistent":
            if not cfg.path:
                raise ValueError(
                    f"ChromaDB backend '{cfg.name}' uses mode=persistent but 'path' is not set."
                )

            def _mk_persistent() -> Any:
                return chromadb.PersistentClient(
                    path=cfg.path,
                    tenant=cfg.tenant,
                    database=cfg.database,
                )

            self._client = await self._run(_mk_persistent)
            self._is_async = False
        else:  # ephemeral
            def _mk_ephemeral() -> Any:
                return chromadb.EphemeralClient(
                    tenant=cfg.tenant,
                    database=cfg.database,
                )

            self._client = await self._run(_mk_ephemeral)
            self._is_async = False

    async def disconnect(self) -> None:
        self._client = None

    # ── Internal helpers ──────────────────────────────────────────────────────

    @property
    def _c(self) -> Any:
        if self._client is None:
            raise RuntimeError(
                f"ChromaAdapter '{self.name}' is not connected. "
                "Call await adapter.connect() first."
            )
        return self._client

    async def _call(self, fn: Any, *args: Any, **kwargs: Any) -> Any:
        """Dispatch a client/collection method — awaited for HTTP, executor for sync modes."""
        if self._is_async:
            return await fn(*args, **kwargs)
        return await self._run(fn, *args, **kwargs)

    async def _get_collection(self, name: str) -> Any:
        return await self._call(self._c.get_collection, name)

    def _collection_space(self, col: Any) -> str:
        metadata = col.metadata or {}
        return metadata.get("hnsw:space", "l2")

    # ── Collections ───────────────────────────────────────────────────────────

    async def list_collections(self) -> list[CollectionInfo]:
        raw_cols = await self._call(self._c.list_collections)
        result: list[CollectionInfo] = []

        for raw in raw_cols:
            name: str = raw.name
            try:
                col = await self._call(self._c.get_collection, name)
                space = self._collection_space(col)
                distance = _METRIC_MAP.get(space, space)

                count = await self._call(col.count)
                dimension = 0
                if count > 0:
                    sample = await self._call(col.peek, 1)
                    embeddings = sample.get("embeddings") or []
                    if embeddings and embeddings[0]:
                        dimension = len(embeddings[0])

                result.append(
                    CollectionInfo(
                        name=name,
                        vector_count=count,
                        dimension=dimension,
                        distance_metric=distance,
                        backend_name=self.name,
                    )
                )
            except Exception as exc:
                result.append(
                    CollectionInfo(
                        name=name,
                        vector_count=0,
                        dimension=0,
                        distance_metric=f"error: {exc}",
                        backend_name=self.name,
                    )
                )

        return result

    async def collection_stats(self, collection: str) -> CollectionStats:
        col = await self._get_collection(collection)
        metadata = col.metadata or {}
        space = metadata.get("hnsw:space", "l2")
        distance = _METRIC_MAP.get(space, space)

        count = await self._call(col.count)

        dimension = 0
        if count > 0:
            sample = await self._call(col.peek, 1)
            embeddings = sample.get("embeddings") or []
            if embeddings and embeddings[0]:
                dimension = len(embeddings[0])

        index_params: dict[str, Any] = {}
        for key, param_name in [
            ("hnsw:construction_ef", "ef_construction"),
            ("hnsw:M", "M"),
            ("hnsw:search_ef", "search_ef"),
            ("hnsw:num_threads", "num_threads"),
        ]:
            if key in metadata:
                index_params[param_name] = metadata[key]

        return CollectionStats(
            name=collection,
            backend_name=self.name,
            vector_count=count,
            dimension=dimension,
            distance_metric=distance,
            index_type="hnsw",
            index_params=index_params,
            raw={
                "hnsw_space": space,
                "collection_metadata": metadata,
                "tenant": self._config.tenant,
                "database": self._config.database,
                "mode": self._config.mode,
            },
        )

    # ── Query ─────────────────────────────────────────────────────────────────

    async def query(self, request: QueryRequest) -> QueryResult:
        col = await self._get_collection(request.collection)
        space = self._collection_space(col)

        chroma_filter = _translate_filter(request.filters) if request.filters else None

        include: list[str] = ["distances", "metadatas"]
        if request.with_vectors:
            include.append("embeddings")

        native_query: dict[str, Any] = {
            "collection": request.collection,
            "query_embeddings": f"[{len(request.vector)}-dim vector]",
            "n_results": request.top_k,
            "include": include,
        }
        if chroma_filter:
            native_query["where"] = chroma_filter

        kwargs: dict[str, Any] = {
            "query_embeddings": [request.vector],
            "n_results": request.top_k,
            "include": include,
        }
        if chroma_filter:
            kwargs["where"] = chroma_filter

        t0 = time.perf_counter()
        response = await self._call(col.query, **kwargs)
        latency_ms = (time.perf_counter() - t0) * 1000

        # Chroma batches results (one list per query vector) — take index 0
        ids: list[str] = (response.get("ids") or [[]])[0]
        distances: list[float] = (response.get("distances") or [[]])[0]
        metadatas: list[dict[str, Any]] = (response.get("metadatas") or [[]])[0]
        embeddings_batch = (response.get("embeddings") or [None])[0]

        hits: list[QueryHit] = []
        for i, doc_id in enumerate(ids):
            score = _distance_to_score(distances[i], space)
            payload = dict(metadatas[i]) if metadatas and metadatas[i] else {}
            vec: list[float] | None = None
            if embeddings_batch and i < len(embeddings_batch):
                vec = list(embeddings_batch[i])
            hits.append(QueryHit(id=str(doc_id), score=score, payload=payload, vector=vec))

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
        col = await self._get_collection(collection)

        response = await self._call(
            col.get,
            ids=ids,
            include=["embeddings", "metadatas"],
        )

        result_ids: list[str] = response.get("ids") or []
        result_embeddings: list[list[float]] = response.get("embeddings") or []
        result_metadatas: list[dict[str, Any]] = response.get("metadatas") or []

        return [
            VectorRecord(
                id=str(result_ids[i]),
                vector=list(result_embeddings[i]) if i < len(result_embeddings) else [],
                payload=(
                    dict(result_metadatas[i])
                    if i < len(result_metadatas) and result_metadatas[i]
                    else {}
                ),
                backend_name=self.name,
            )
            for i in range(len(result_ids))
        ]

    # ── Health ────────────────────────────────────────────────────────────────

    async def health(self, collection: str) -> HealthReport:
        findings: list[HealthFinding] = []
        t0 = time.perf_counter()

        # ── 1. Reachability ───────────────────────────────────────────────────
        try:
            await self._call(self._c.list_collections)
        except Exception as exc:
            return HealthReport(
                backend_name=self.name,
                collection=collection,
                status="unhealthy",
                findings=[
                    HealthFinding(
                        severity="error",
                        code="unreachable",
                        message="Cannot connect to ChromaDB.",
                        detail=str(exc),
                        recommendation=(
                            "Verify ChromaDB is running and the host/port in vlens.yaml are correct. "
                            "For HTTP mode: `chroma run --path /data`. "
                            "For persistent mode: verify the path exists and is writable."
                        ),
                    )
                ],
                latency_ms=round((time.perf_counter() - t0) * 1000, 3),
            )

        # ── 2. Collection exists ──────────────────────────────────────────────
        try:
            stats = await self.collection_stats(collection)
        except Exception as exc:
            return HealthReport(
                backend_name=self.name,
                collection=collection,
                status="unhealthy",
                findings=[
                    HealthFinding(
                        severity="error",
                        code="collection_not_found",
                        message=f"Collection '{collection}' not found in ChromaDB.",
                        detail=str(exc),
                        recommendation=(
                            "Check the collection name. "
                            "List available collections with: client.list_collections()"
                        ),
                    )
                ],
                latency_ms=round((time.perf_counter() - t0) * 1000, 3),
            )

        # ── 3. Empty collection ───────────────────────────────────────────────
        if stats.vector_count == 0:
            findings.append(
                HealthFinding(
                    severity="warning",
                    code="empty_collection",
                    message=f"Collection '{collection}' contains no vectors.",
                    detail="count=0",
                    recommendation="Add vectors with collection.add() before running queries.",
                )
            )

        # ── 4. HNSW ef_construction ───────────────────────────────────────────
        ef = stats.index_params.get("ef_construction")
        if ef is not None:
            if ef < 64:
                findings.append(
                    HealthFinding(
                        severity="error",
                        code="hnsw_ef_construct_too_low",
                        message=f"HNSW ef_construction={ef} is very low — recall will be poor.",
                        detail=f"ef_construction={ef}",
                        recommendation=(
                            "Set hnsw:construction_ef >= 100 when creating the collection. "
                            "This parameter cannot be changed after creation — recreate the collection."
                        ),
                    )
                )
            elif ef < 100 and stats.vector_count > 10_000:
                findings.append(
                    HealthFinding(
                        severity="warning",
                        code="hnsw_ef_construct_marginal",
                        message=(
                            f"HNSW ef_construction={ef} may be too low "
                            f"for {stats.vector_count:,} vectors."
                        ),
                        detail=f"ef_construction={ef}, vector_count={stats.vector_count}",
                        recommendation=(
                            "Consider ef_construction >= 100 for better recall on large collections."
                        ),
                    )
                )

        # ── 5. HNSW M parameter ───────────────────────────────────────────────
        m = stats.index_params.get("M")
        if m is not None and m < 4:
            findings.append(
                HealthFinding(
                    severity="warning",
                    code="hnsw_m_too_low",
                    message=f"HNSW M={m} is below the recommended minimum of 4.",
                    detail=f"M={m}",
                    recommendation=(
                        "M controls graph connectivity and recall. "
                        "ChromaDB default is 16; values below 4 hurt recall significantly."
                    ),
                )
            )

        # ── 6. L2 distance metric advisory ────────────────────────────────────
        space = stats.raw.get("hnsw_space", "l2")
        if space == "l2" and stats.vector_count > 0:
            findings.append(
                HealthFinding(
                    severity="info",
                    code="l2_distance_metric",
                    message="Collection uses L2 (Euclidean) distance.",
                    detail=f"hnsw:space={space}",
                    recommendation=(
                        "For RAG workloads with normalised embeddings (e.g. OpenAI, Cohere), "
                        "cosine similarity typically gives better results. "
                        "Set hnsw:space='cosine' when creating the collection."
                    ),
                )
            )

        severities = {f.severity for f in findings}
        status = (
            "unhealthy"
            if "error" in severities
            else "degraded"
            if "warning" in severities
            else "healthy"
        )

        return HealthReport(
            backend_name=self.name,
            collection=collection,
            status=status,
            findings=findings,
            stats=stats,
            latency_ms=round((time.perf_counter() - t0) * 1000, 3),
        )


__all__ = ["ChromaAdapter"]
