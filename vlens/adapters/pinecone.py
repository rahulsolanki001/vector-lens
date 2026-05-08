"""
vlens.adapters.pinecone — Pinecone adapter (SDK v3-v8).

Install: pip install vector-lens[pinecone]

Supports:
  - Serverless and pod-based Pinecone indexes
  - Namespace-scoped queries
  - Vector Lens canonical filter → Pinecone metadata-filter translation
"""

from __future__ import annotations

import asyncio
import functools
import time
from typing import Any

try:
    from pinecone import Pinecone
except ImportError as exc:
    raise ImportError(
        "pinecone is required for the Pinecone adapter.\n"
        "Install it with: pip install vector-lens[pinecone]"
    ) from exc

from vlens.adapters.base import (
    CollectionInfo,
    CollectionStats,
    HealthFinding,
    HealthReport,
    PineconeConfig,
    QueryHit,
    QueryRequest,
    QueryResult,
    VecDBAdapter,
    VectorRecord,
)

# ── Metric mapping ────────────────────────────────────────────────────────────

_METRIC_MAP: dict[str, str] = {
    "cosine": "cosine",
    "euclidean": "euclidean",
    "dotproduct": "dot",
}

# ── Filter translation ────────────────────────────────────────────────────────


def _translate_filter(filters: dict[str, Any]) -> dict[str, Any]:
    """
    Translate a Vector Lens canonical filter dict → Pinecone metadata filter dict.

    Pinecone uses a MongoDB-style filter format. The translation is mostly
    1:1 except:
      - Direct equality {"field": val} → {"field": {"$eq": val}}
      - Vector Lens $not → Pinecone $nor (Pinecone doesn't support top-level $not)
    All other operators ($gt, $gte, $lt, $lte, $in, $ne) pass through unchanged.
    """
    result: dict[str, Any] = {}
    for key, value in filters.items():
        if key == "$and":
            result["$and"] = [_translate_filter(sub) for sub in value]
        elif key == "$or":
            result["$or"] = [_translate_filter(sub) for sub in value]
        elif key == "$not":
            result["$nor"] = [_translate_filter(value)]
        elif isinstance(value, dict):
            result[key] = value
        else:
            result[key] = {"$eq": value}
    return result


# ── Adapter ───────────────────────────────────────────────────────────────────


class PineconeAdapter(VecDBAdapter):
    """
    Pinecone implementation of VecDBAdapter (SDK v3+).

    The Pinecone Python SDK is synchronous. Every call is dispatched to a
    thread-pool executor so the async FastAPI event loop is never blocked.
    """

    def __init__(self, config: PineconeConfig) -> None:
        self._config = config
        self._pc: Pinecone | None = None

    # ── Identity ──────────────────────────────────────────────────────────────

    @property
    def name(self) -> str:
        return self._config.name

    @property
    def backend_type(self) -> str:
        return "pinecone"

    # ── Executor helper ───────────────────────────────────────────────────────

    async def _run(self, fn: Any, *args: Any, **kwargs: Any) -> Any:
        """Run a synchronous callable in the default thread-pool executor."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, functools.partial(fn, *args, **kwargs))

    # ── Internal ──────────────────────────────────────────────────────────────

    @property
    def _client(self) -> Pinecone:
        if self._pc is None:
            raise RuntimeError(
                f"PineconeAdapter '{self.name}' is not connected. "
                "Call await adapter.connect() first."
            )
        return self._pc

    def _index(self, index_name: str) -> Any:
        """Return a connected Index handle for the given index name."""
        return self._client.Index(name=index_name)

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def connect(self) -> None:
        cfg = self._config

        def _connect() -> Pinecone:
            return Pinecone(api_key=cfg.api_key)

        self._pc = await self._run(_connect)

    async def disconnect(self) -> None:
        self._pc = None

    # ── Collections ───────────────────────────────────────────────────────────

    async def list_collections(self) -> list[CollectionInfo]:
        """List all Pinecone indexes as Vector Lens collections."""
        index_list = await self._run(self._client.list_indexes)
        result: list[CollectionInfo] = []

        for idx in index_list:
            try:
                idx_name: str = idx.name
                dimension: int = idx.dimension or 0
                metric: str = _METRIC_MAP.get(idx.metric, idx.metric or "cosine")
                count = 0
                try:
                    handle = self._index(idx_name)
                    stats = await self._run(handle.describe_index_stats)
                    count = stats.total_vector_count or 0
                except Exception:
                    pass
                result.append(
                    CollectionInfo(
                        name=idx_name,
                        vector_count=count,
                        dimension=dimension,
                        distance_metric=metric,
                        backend_name=self.name,
                    )
                )
            except Exception as exc:
                result.append(
                    CollectionInfo(
                        name=str(getattr(idx, "name", "unknown")),
                        vector_count=0,
                        dimension=0,
                        distance_metric=f"error: {exc}",
                        backend_name=self.name,
                    )
                )

        return result

    async def collection_stats(self, collection: str) -> CollectionStats:
        idx_desc = await self._run(self._client.describe_index, collection)
        handle = self._index(collection)
        raw_stats = await self._run(handle.describe_index_stats)

        dimension: int = idx_desc.dimension or 0
        metric: str = _METRIC_MAP.get(idx_desc.metric, idx_desc.metric or "cosine")
        count: int = raw_stats.total_vector_count or 0

        # Determine spec type and params (serverless vs pod)
        spec_type = "serverless"
        index_params: dict[str, Any] = {}
        spec = getattr(idx_desc, "spec", None)
        if spec is not None:
            sl = getattr(spec, "serverless", None)
            pod = getattr(spec, "pod", None)
            if sl is not None:
                spec_type = "serverless"
                index_params = {
                    "cloud": getattr(sl, "cloud", "unknown"),
                    "region": getattr(sl, "region", "unknown"),
                }
            elif pod is not None:
                spec_type = "pod"
                index_params = {
                    "pod_type": getattr(pod, "pod_type", "unknown"),
                    "pods": getattr(pod, "pods", 1),
                    "replicas": getattr(pod, "replicas", 1),
                    "shards": getattr(pod, "shards", 1),
                }

        # Namespace summary
        namespaces: dict[str, int] = {}
        if raw_stats.namespaces:
            for ns, ns_info in raw_stats.namespaces.items():
                namespaces[ns] = getattr(ns_info, "vector_count", 0)

        status_obj = getattr(idx_desc, "status", None)
        index_fullness = getattr(raw_stats, "index_fullness", None)

        return CollectionStats(
            name=collection,
            backend_name=self.name,
            vector_count=count,
            dimension=dimension,
            distance_metric=metric,
            index_type=spec_type,
            index_params=index_params,
            raw={
                "index_fullness": index_fullness,
                "namespaces": namespaces,
                "status_state": str(getattr(status_obj, "state", "unknown")),
                "status_ready": bool(getattr(status_obj, "ready", True)),
                "host": getattr(idx_desc, "host", ""),
            },
        )

    # ── Query ─────────────────────────────────────────────────────────────────

    async def query(self, request: QueryRequest) -> QueryResult:
        handle = self._index(request.collection)
        pinecone_filter = _translate_filter(request.filters) if request.filters else None
        namespace = self._config.namespace

        native_query: dict[str, Any] = {
            "index": request.collection,
            "top_k": request.top_k,
            "include_metadata": request.with_payload,
            "include_values": request.with_vectors,
            "vector": f"[{len(request.vector)}-dim vector]",
        }
        if namespace:
            native_query["namespace"] = namespace
        if pinecone_filter:
            native_query["filter"] = pinecone_filter

        t0 = time.perf_counter()

        def _query() -> Any:
            kwargs: dict[str, Any] = {
                "vector": request.vector,
                "top_k": request.top_k,
                "include_metadata": request.with_payload,
                "include_values": request.with_vectors,
            }
            if namespace:
                kwargs["namespace"] = namespace
            if pinecone_filter:
                kwargs["filter"] = pinecone_filter
            return handle.query(**kwargs)

        response = await self._run(_query)
        latency_ms = (time.perf_counter() - t0) * 1000

        hits: list[QueryHit] = []
        for match in response.matches or []:
            vec: list[float] | None = None
            if request.with_vectors and match.values:
                vec = list(match.values)
            hits.append(
                QueryHit(
                    id=str(match.id),
                    score=float(match.score),
                    payload=dict(match.metadata) if match.metadata else {},
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
        handle = self._index(collection)
        namespace = self._config.namespace

        def _fetch() -> Any:
            kwargs: dict[str, Any] = {"ids": ids}
            if namespace:
                kwargs["namespace"] = namespace
            return handle.fetch(**kwargs)

        response = await self._run(_fetch)

        records: list[VectorRecord] = []
        vectors_dict: dict[str, Any] = response.vectors or {}
        for vid, vec_obj in vectors_dict.items():
            values = list(vec_obj.values) if vec_obj.values else []
            payload = dict(vec_obj.metadata) if vec_obj.metadata else {}
            records.append(
                VectorRecord(
                    id=str(vid),
                    vector=values,
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
            await self._run(self._client.list_indexes)
        except Exception as exc:
            return HealthReport(
                backend_name=self.name,
                collection=collection,
                status="unhealthy",
                findings=[
                    HealthFinding(
                        severity="error",
                        code="unreachable",
                        message="Cannot connect to Pinecone API.",
                        detail=str(exc),
                        recommendation=(
                            "Check that your api_key in vlens.yaml is valid "
                            "and that you have internet access to api.pinecone.io."
                        ),
                    )
                ],
                latency_ms=round((time.perf_counter() - t0) * 1000, 3),
            )

        # ── 2. Index exists ───────────────────────────────────────────────────
        all_indexes = await self._run(self._client.list_indexes)
        index_names = [idx.name for idx in all_indexes]
        if collection not in index_names:
            return HealthReport(
                backend_name=self.name,
                collection=collection,
                status="unhealthy",
                findings=[
                    HealthFinding(
                        severity="error",
                        code="collection_not_found",
                        message=f"Pinecone index '{collection}' does not exist.",
                        detail=f"Available indexes: {index_names or 'none'}",
                        recommendation=(
                            "Check the index name in vlens.yaml or create the index first."
                        ),
                    )
                ],
                latency_ms=round((time.perf_counter() - t0) * 1000, 3),
            )

        # ── 3. Collect stats ──────────────────────────────────────────────────
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
                        message="Failed to retrieve index stats.",
                        detail=str(exc),
                        recommendation="Check Pinecone API status at status.pinecone.io.",
                    )
                ],
                latency_ms=round((time.perf_counter() - t0) * 1000, 3),
            )

        # ── 4. Index ready ────────────────────────────────────────────────────
        if not stats.raw.get("status_ready", True):
            state = stats.raw.get("status_state", "unknown")
            findings.append(
                HealthFinding(
                    severity="error",
                    code="index_not_ready",
                    message=f"Pinecone index '{collection}' is not ready (state: {state}).",
                    detail=f"status.state={state}",
                    recommendation=(
                        "Wait for the index to finish initialising before running queries."
                    ),
                )
            )

        # ── 5. Index fullness ─────────────────────────────────────────────────
        fullness = stats.raw.get("index_fullness")
        if fullness is not None:
            if fullness > 0.9:
                findings.append(
                    HealthFinding(
                        severity="error",
                        code="index_nearly_full",
                        message=f"Index is {fullness * 100:.0f}% full — writes will be rejected soon.",
                        detail=f"index_fullness={fullness:.3f}",
                        recommendation=(
                            "Upgrade your pod tier or delete unused vectors. "
                            "Serverless indexes auto-scale; pod indexes have a fixed capacity."
                        ),
                    )
                )
            elif fullness > 0.75:
                findings.append(
                    HealthFinding(
                        severity="warning",
                        code="index_high_fullness",
                        message=f"Index is {fullness * 100:.0f}% full.",
                        detail=f"index_fullness={fullness:.3f}",
                        recommendation="Plan capacity expansion before the index fills up.",
                    )
                )

        # ── 6. Empty index ────────────────────────────────────────────────────
        if stats.vector_count == 0:
            findings.append(
                HealthFinding(
                    severity="warning",
                    code="empty_collection",
                    message=f"Pinecone index '{collection}' contains no vectors.",
                    detail="total_vector_count=0",
                    recommendation="Upsert vectors before running queries.",
                )
            )

        # ── Overall status ────────────────────────────────────────────────────
        severities = {f.severity for f in findings}
        status = (
            "unhealthy"
            if "error" in severities
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


__all__ = ["PineconeAdapter"]
