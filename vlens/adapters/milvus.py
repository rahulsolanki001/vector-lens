"""
vlens.adapters.milvus — Milvus / Zilliz Cloud adapter.

Install: pip install vector-lens[milvus]

Supports:
  - Local Milvus (host/port → http://host:port)
  - Zilliz Cloud (host=full-URL + token=user:password or API key)
  - HNSW, IVF_FLAT, IVF_SQ8, IVF_PQ, DISKANN index types
  - Vector Lens canonical filter → Milvus expression-string translation
"""

from __future__ import annotations

import asyncio
import functools
import time
from typing import Any

try:
    from pymilvus import MilvusClient
except ImportError as exc:
    raise ImportError(
        "pymilvus is required for the Milvus adapter.\n"
        "Install it with: pip install vector-lens[milvus]"
    ) from exc

from vlens.adapters.base import (
    CollectionInfo,
    CollectionStats,
    HealthFinding,
    HealthReport,
    MilvusConfig,
    QueryHit,
    QueryRequest,
    QueryResult,
    VecDBAdapter,
    VectorRecord,
)

# ── Distance metric mapping ───────────────────────────────────────────────────

_METRIC_MAP: dict[str, str] = {
    "L2":     "euclidean",
    "IP":     "dot",
    "COSINE": "cosine",
}

_METRIC_MAP_INV: dict[str, str] = {v: k for k, v in _METRIC_MAP.items()}

# ── Filter translation ────────────────────────────────────────────────────────


def _literal(v: Any) -> str:
    """Format a Python value as a Milvus expression literal."""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, str):
        return '"' + v.replace("\\", "\\\\").replace('"', '\\"') + '"'
    return str(v)


def _build_expr(filters: dict[str, Any]) -> str:
    """
    Translate a Vector Lens canonical filter dict → Milvus expression string.

    Vector Lens canonical DSL:
        {"field": "value"}                    → field == "value"
        {"field": {"$gt": 0.5}}               → field > 0.5
        {"field": {"$in": ["a", "b"]}}        → field in ["a", "b"]
        {"$and": [cond1, cond2]}              → (cond1) and (cond2)
        {"$or": [cond1, cond2]}               → (cond1) or (cond2)
        {"$not": cond}                        → not (cond)
    """
    parts: list[str] = []
    for key, value in filters.items():
        if key == "$and":
            subs = [f"({_build_expr(sub)})" for sub in value]
            parts.append(" and ".join(subs))
        elif key == "$or":
            subs = [f"({_build_expr(sub)})" for sub in value]
            parts.append(" or ".join(subs))
        elif key == "$not":
            parts.append(f"not ({_build_expr(value)})")
        elif isinstance(value, dict):
            for op, operand in value.items():
                match op:
                    case "$gt":
                        parts.append(f"{key} > {_literal(operand)}")
                    case "$gte":
                        parts.append(f"{key} >= {_literal(operand)}")
                    case "$lt":
                        parts.append(f"{key} < {_literal(operand)}")
                    case "$lte":
                        parts.append(f"{key} <= {_literal(operand)}")
                    case "$in":
                        vals = ", ".join(_literal(v) for v in operand)
                        parts.append(f"{key} in [{vals}]")
                    case _:
                        raise ValueError(
                            f"Unsupported filter operator '{op}' on field '{key}'. "
                            "Supported: $gt, $gte, $lt, $lte, $in"
                        )
        else:
            parts.append(f"{key} == {_literal(value)}")
    return " and ".join(parts) if parts else ""


# ── Schema helpers ────────────────────────────────────────────────────────────


def _is_float_vector(ftype: Any) -> bool:
    """True if ftype represents a FLOAT_VECTOR field (handles enum/int/str)."""
    return "FLOAT_VECTOR" in str(ftype) or ftype == 101


def _parse_schema(desc: dict[str, Any]) -> tuple[str, str, int]:
    """
    Return (pk_field, vector_field, dimension) from a describe_collection dict.

    The describe_collection response in pymilvus 2.4 looks like:
        {"fields": [{"name": "id", "type": DataType.INT64, "is_primary": True}, ...]}
    The type may be a DataType enum, an int, or a string — we handle all three.
    """
    pk_field = "id"
    vec_field = "vector"
    dim = 0

    for field in desc.get("fields", []):
        if field.get("is_primary"):
            pk_field = field["name"]
        if _is_float_vector(field.get("type")):
            vec_field = field["name"]
            dim = int(field.get("params", {}).get("dim", 0))

    return pk_field, vec_field, dim


def _hit_to_parts(hit: Any) -> tuple[Any, float, dict[str, Any]]:
    """
    Extract (id, distance, entity) from a search hit.

    pymilvus 2.4 MilvusClient returns hits as dicts with "id", "distance",
    "entity" keys. Guard against older object-style hits just in case.
    """
    if isinstance(hit, dict):
        return hit["id"], float(hit.get("distance", 0.0)), hit.get("entity", {})
    return hit.id, float(hit.distance), dict(hit.entity) if hasattr(hit, "entity") else {}


# ── Adapter ───────────────────────────────────────────────────────────────────


class MilvusAdapter(VecDBAdapter):
    """
    Milvus implementation of VecDBAdapter.

    pymilvus is a synchronous SDK. Every call is dispatched to a thread-pool
    executor so the async FastAPI event loop is never blocked.
    """

    def __init__(self, config: MilvusConfig) -> None:
        self._config = config
        self._client: MilvusClient | None = None

    # ── Identity ──────────────────────────────────────────────────────────────

    @property
    def name(self) -> str:
        return self._config.name

    @property
    def backend_type(self) -> str:
        return "milvus"

    # ── Executor helper ───────────────────────────────────────────────────────

    async def _run(self, fn: Any, *args: Any, **kwargs: Any) -> Any:
        """Run a synchronous callable in the default thread-pool executor."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, functools.partial(fn, *args, **kwargs))

    # ── Internal ──────────────────────────────────────────────────────────────

    @property
    def _c(self) -> MilvusClient:
        if self._client is None:
            raise RuntimeError(
                f"MilvusAdapter '{self.name}' is not connected. "
                "Call await adapter.connect() first."
            )
        return self._client

    def _make_uri(self) -> str:
        cfg = self._config
        # Allow host to be a full URL (Zilliz Cloud passes https://... directly)
        if cfg.host.startswith("http://") or cfg.host.startswith("https://"):
            return cfg.host
        return f"http://{cfg.host}:{cfg.port}"

    def _describe(self, collection: str) -> dict[str, Any]:
        raw = self._c.describe_collection(collection)
        # pymilvus ≥ 2.4: returns dict directly; older: might be a Pydantic model
        return dict(raw) if not isinstance(raw, dict) else raw

    def _get_metric(self, collection: str, vec_field: str) -> str:
        """Detect metric type from the vector index on this collection."""
        try:
            index_names: list[str] = self._c.list_indexes(collection)
            for idx_name in index_names:
                info = self._c.describe_index(collection, idx_name)
                if not isinstance(info, dict):
                    info = dict(info)
                if info.get("field_name") == vec_field or info.get("field") == vec_field:
                    raw_metric = info.get("metric_type", "L2")
                    return _METRIC_MAP.get(str(raw_metric), "euclidean")
        except Exception:
            pass
        return "euclidean"

    def _row_count(self, collection: str) -> int:
        try:
            stats = self._c.get_collection_stats(collection)
            if isinstance(stats, dict):
                return int(stats.get("row_count", 0))
            return int(getattr(stats, "row_count", 0))
        except Exception:
            return 0

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def connect(self) -> None:
        cfg = self._config
        uri = self._make_uri()

        def _connect() -> MilvusClient:
            kwargs: dict[str, Any] = {"uri": uri}
            if cfg.token:
                kwargs["token"] = cfg.token
            return MilvusClient(**kwargs)

        self._client = await self._run(_connect)

    async def disconnect(self) -> None:
        if self._client is not None:
            try:
                await self._run(self._client.close)
            except Exception:
                pass
            self._client = None

    # ── Collections ───────────────────────────────────────────────────────────

    async def list_collections(self) -> list[CollectionInfo]:
        names: list[str] = await self._run(self._c.list_collections)
        result: list[CollectionInfo] = []

        for name in names:
            try:
                desc = await self._run(self._describe, name)
                _, vec_field, dim = _parse_schema(desc)
                metric = await self._run(self._get_metric, name, vec_field)
                count = await self._run(self._row_count, name)
                result.append(
                    CollectionInfo(
                        name=name,
                        vector_count=count,
                        dimension=dim,
                        distance_metric=metric,
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
        desc = await self._run(self._describe, collection)
        pk_field, vec_field, dim = _parse_schema(desc)
        metric = await self._run(self._get_metric, collection, vec_field)
        count = await self._run(self._row_count, collection)

        # Index info
        index_type = "none"
        index_params: dict[str, Any] = {}
        try:
            idx_names: list[str] = await self._run(self._c.list_indexes, collection)
            for idx_name in idx_names:
                info = await self._run(self._c.describe_index, collection, idx_name)
                if not isinstance(info, dict):
                    info = dict(info)
                fld = info.get("field_name") or info.get("field", "")
                if fld == vec_field:
                    index_type = str(info.get("index_type", "none")).lower()
                    index_params = dict(info.get("params", {}))
                    break
        except Exception:
            pass

        # Load state
        load_state = "unknown"
        try:
            state_resp = await self._run(self._c.get_load_state, collection)
            if isinstance(state_resp, dict):
                load_state = str(state_resp.get("state", "unknown"))
            else:
                load_state = str(state_resp)
        except Exception:
            pass

        return CollectionStats(
            name=collection,
            backend_name=self.name,
            vector_count=count,
            dimension=dim,
            distance_metric=metric,
            index_type=index_type,
            index_params=index_params,
            raw={
                "pk_field": pk_field,
                "vector_field": vec_field,
                "load_state": load_state,
                "num_shards": desc.get("num_shards"),
                "num_replicas": desc.get("num_replicas"),
            },
        )

    # ── Query ─────────────────────────────────────────────────────────────────

    async def query(self, request: QueryRequest) -> QueryResult:
        desc = await self._run(self._describe, request.collection)
        _, vec_field, _ = _parse_schema(desc)

        expr = _build_expr(request.filters) if request.filters else ""

        output_fields: list[str] = ["*"] if request.with_payload else []
        if request.with_vectors:
            output_fields = list(set(output_fields) | {vec_field})

        native_query: dict[str, Any] = {
            "collection": request.collection,
            "anns_field": vec_field,
            "data": f"[{len(request.vector)}-dim vector]",
            "limit": request.top_k,
        }
        if expr:
            native_query["filter"] = expr
        if output_fields:
            native_query["output_fields"] = output_fields

        t0 = time.perf_counter()

        def _search() -> Any:
            kwargs: dict[str, Any] = {
                "collection_name": request.collection,
                "data": [request.vector],
                "anns_field": vec_field,
                "limit": request.top_k,
                "output_fields": output_fields or ["*"],
            }
            if expr:
                kwargs["filter"] = expr
            return self._c.search(**kwargs)

        raw = await self._run(_search)
        latency_ms = (time.perf_counter() - t0) * 1000

        hits: list[QueryHit] = []
        # raw is list[list[hit_dict]] — one inner list per query vector
        for hit in raw[0] if raw else []:
            hit_id, distance, entity = _hit_to_parts(hit)
            payload = {k: v for k, v in entity.items() if k != vec_field}
            vec: list[float] | None = None
            if request.with_vectors and vec_field in entity:
                raw_vec = entity[vec_field]
                vec = [float(x) for x in raw_vec] if raw_vec is not None else None

            hits.append(
                QueryHit(
                    id=str(hit_id),
                    score=float(distance),
                    payload=payload,
                    vector=vec,
                )
            )

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
        desc = await self._run(self._describe, collection)
        pk_field, vec_field, _ = _parse_schema(desc)

        # Cast IDs to int if the PK is numeric (Milvus default auto-ID is INT64)
        def _cast_id(raw: str) -> Any:
            try:
                return int(raw)
            except ValueError:
                return raw

        milvus_ids = [_cast_id(i) for i in ids]

        def _fetch() -> list[dict[str, Any]]:
            # Build an ID filter expression that works for both int and string PKs
            if milvus_ids and isinstance(milvus_ids[0], int):
                id_expr = f"{pk_field} in [{', '.join(str(i) for i in milvus_ids)}]"
            else:
                quoted = ", ".join(f'"{i}"' for i in milvus_ids)
                id_expr = f"{pk_field} in [{quoted}]"

            result: list[dict[str, Any]] = self._c.query(
                collection_name=collection,
                filter=id_expr,
                output_fields=[vec_field, "*"],
            )
            return result

        rows: list[dict[str, Any]] = await self._run(_fetch)

        records: list[VectorRecord] = []
        for row in rows:
            raw_vec = row.get(vec_field)
            vector = [float(x) for x in raw_vec] if raw_vec is not None else []
            payload = {k: v for k, v in row.items() if k not in (pk_field, vec_field)}
            records.append(
                VectorRecord(
                    id=str(row.get(pk_field, "")),
                    vector=vector,
                    payload=payload,
                    backend_name=self.name,
                )
            )

        return records

    # ── Health ────────────────────────────────────────────────────────────────

    async def health(self, collection: str) -> HealthReport:
        findings: list[HealthFinding] = []
        t0 = time.perf_counter()

        # ── 1. Reachability ───────────────────────────────────────────────────
        try:
            await self._run(self._c.list_collections)
        except Exception as exc:
            return HealthReport(
                backend_name=self.name,
                collection=collection,
                status="unhealthy",
                findings=[
                    HealthFinding(
                        severity="error",
                        code="unreachable",
                        message="Cannot connect to Milvus.",
                        detail=str(exc),
                        recommendation=(
                            "Check that Milvus is running and the host/port in vlens.yaml are correct. "
                            "For Zilliz Cloud, verify your token and that the host URL is the full endpoint."
                        ),
                    )
                ],
                latency_ms=round((time.perf_counter() - t0) * 1000, 3),
            )

        # ── 2. Collection exists ──────────────────────────────────────────────
        try:
            all_cols: list[str] = await self._run(self._c.list_collections)
        except Exception:
            all_cols = []

        if collection not in all_cols:
            return HealthReport(
                backend_name=self.name,
                collection=collection,
                status="unhealthy",
                findings=[
                    HealthFinding(
                        severity="error",
                        code="collection_not_found",
                        message=f"Collection '{collection}' does not exist.",
                        detail=f"Available: {all_cols or 'none'}",
                        recommendation="Check the collection name in vlens.yaml.",
                    )
                ],
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
                findings=[
                    HealthFinding(
                        severity="error",
                        code="stats_error",
                        message="Failed to retrieve collection stats.",
                        detail=str(exc),
                        recommendation="Check Milvus logs for schema or permission errors.",
                    )
                ],
                latency_ms=round((time.perf_counter() - t0) * 1000, 3),
            )

        # ── 3. Load state ─────────────────────────────────────────────────────
        load_state = str(stats.raw.get("load_state", "unknown")).lower()
        if "notload" in load_state or "not_load" in load_state:
            findings.append(
                HealthFinding(
                    severity="error",
                    code="collection_not_loaded",
                    message=f"Collection '{collection}' is not loaded into memory.",
                    detail=f"load_state={load_state}",
                    recommendation=(
                        "Load the collection before querying: "
                        "client.load_collection(collection_name)"
                    ),
                )
            )
        elif "loading" in load_state:
            findings.append(
                HealthFinding(
                    severity="warning",
                    code="collection_loading",
                    message=f"Collection '{collection}' is still loading.",
                    detail=f"load_state={load_state}",
                    recommendation="Wait for loading to complete before running queries.",
                )
            )

        # ── 4. Index present ──────────────────────────────────────────────────
        if stats.index_type in ("none", ""):
            findings.append(
                HealthFinding(
                    severity="warning",
                    code="no_vector_index",
                    message="No vector index found on this collection.",
                    detail=f"vector_field={stats.raw.get('vector_field')}",
                    recommendation=(
                        "Create an index for ANN search:\n"
                        "  collection.create_index(field_name, index_params)\n"
                        "Without an index, every query falls back to brute-force scan."
                    ),
                )
            )

        # ── 5. HNSW ef_construct ──────────────────────────────────────────────
        if stats.index_type == "hnsw":
            ef_construct = int(stats.index_params.get("efConstruction", 0))
            M = int(stats.index_params.get("M", 0))
            if ef_construct and ef_construct < 64:
                findings.append(
                    HealthFinding(
                        severity="error",
                        code="hnsw_ef_construct_too_low",
                        message=f"HNSW efConstruction={ef_construct} is very low — recall will be poor.",
                        detail=f"efConstruction={ef_construct}",
                        recommendation="Set efConstruction >= 100 for production workloads.",
                    )
                )
            elif ef_construct and ef_construct < 128 and stats.vector_count > 100_000:
                findings.append(
                    HealthFinding(
                        severity="warning",
                        code="hnsw_ef_construct_marginal",
                        message=(
                            f"HNSW efConstruction={ef_construct} may be low "
                            f"for {stats.vector_count:,} vectors."
                        ),
                        detail=f"efConstruction={ef_construct}, vectors={stats.vector_count}",
                        recommendation="Consider efConstruction >= 128 for large collections.",
                    )
                )
            if M and M < 8:
                findings.append(
                    HealthFinding(
                        severity="warning",
                        code="hnsw_m_too_low",
                        message=f"HNSW M={M} is below the recommended minimum of 8.",
                        detail=f"M={M}",
                        recommendation="M controls graph connectivity — values < 8 reduce recall. Default is 16.",
                    )
                )

        # ── 6. IVF nlist sanity ───────────────────────────────────────────────
        if stats.index_type in ("ivf_flat", "ivf_sq8", "ivf_pq"):
            nlist = int(stats.index_params.get("nlist", 0))
            if nlist and stats.vector_count and stats.vector_count < nlist * 39:
                findings.append(
                    HealthFinding(
                        severity="warning",
                        code="ivf_nlist_too_large",
                        message=f"nlist={nlist} is large relative to the collection size ({stats.vector_count:,} vectors).",
                        detail=f"nlist={nlist}, vector_count={stats.vector_count}",
                        recommendation=(
                            "A rule of thumb is nlist ≈ sqrt(vector_count). "
                            f"For {stats.vector_count:,} vectors, consider nlist ≈ {int(stats.vector_count**0.5)}."
                        ),
                    )
                )

        # ── 7. Empty collection ───────────────────────────────────────────────
        if stats.vector_count == 0:
            findings.append(
                HealthFinding(
                    severity="warning",
                    code="empty_collection",
                    message=f"Collection '{collection}' contains no vectors.",
                    detail="row_count=0",
                    recommendation="Insert data before running queries.",
                )
            )

        # ── Overall status ────────────────────────────────────────────────────
        severities = {f.severity for f in findings}
        status = (
            "unhealthy" if "error" in severities
            else ("degraded" if "warning" in severities else "healthy")
        )

        return HealthReport(
            backend_name=self.name,
            collection=collection,
            status=status,
            findings=findings,
            stats=stats,
            latency_ms=round((time.perf_counter() - t0) * 1000, 3),
        )


__all__ = ["MilvusAdapter"]
