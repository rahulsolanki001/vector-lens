"""
vara.adapters.pgvector — asyncpg + pgvector adapter.

Install: pip install vara[pgvector]

Supports:
  - HNSW and IVFFlat indexes (auto-detected from pg_indexes)
  - Cosine (<=>), dot product (<#>), and L2 (<->) distance metrics
  - Vara canonical filter translation → parameterised SQL WHERE clause
"""

from __future__ import annotations

import time
from typing import Any

try:
    import asyncpg
except ImportError as exc:
    raise ImportError(
        "asyncpg is required for the pgvector adapter.\n"
        "Install it with: pip install vara[pgvector]"
    ) from exc

from vara.adapters.base import (
    CollectionInfo,
    CollectionStats,
    HealthFinding,
    HealthReport,
    PgvectorConfig,
    QueryHit,
    QueryRequest,
    QueryResult,
    VecDBAdapter,
    VectorRecord,
)

# ── Distance metric helpers ───────────────────────────────────────────────────

# pgvector index operator class → Vara distance metric name
_OP_TO_METRIC: dict[str, str] = {
    "vector_cosine_ops": "cosine",
    "vector_ip_ops":     "dot",
    "vector_l2_ops":     "euclidean",
}


def _score_expr(metric: str, col: str) -> str:
    """SQL expression that produces a higher-is-better similarity score."""
    if metric == "cosine":
        return f'1.0 - ("{col}" <=> $1::vector)'
    if metric == "dot":
        return f'-("{col}" <#> $1::vector)'
    return f'1.0 / (1.0 + ("{col}" <-> $1::vector))'


def _order_expr(metric: str, col: str) -> str:
    """SQL ORDER BY expression — ascending = most similar first."""
    if metric == "cosine":
        return f'"{col}" <=> $1::vector'
    if metric == "dot":
        return f'"{col}" <#> $1::vector'
    return f'"{col}" <-> $1::vector'


def _detect_metric(index_rows: list[Any]) -> str:
    for row in index_rows:
        indexdef = row["indexdef"].lower()
        for op, metric in _OP_TO_METRIC.items():
            if op in indexdef:
                return metric
    return "cosine"


# ── Filter translation ────────────────────────────────────────────────────────

def _build_where(
    filters: dict[str, Any],
    params: list[Any],
) -> str:
    """
    Translate Vara canonical filter dict → SQL WHERE fragment.

    Parameters are appended to `params` and referenced as $N in the returned
    string. The caller is responsible for passing params to asyncpg.

    Note: param index starts after $1 (reserved for the query vector).
    """
    parts: list[str] = []

    for key, value in filters.items():
        if key == "$and":
            sub = [f"({_build_where(sub, params)})" for sub in value]
            parts.append(" AND ".join(sub))
        elif key == "$or":
            sub = [f"({_build_where(sub, params)})" for sub in value]
            parts.append(" OR ".join(sub))
        elif key == "$not":
            parts.append(f"NOT ({_build_where(value, params)})")
        elif isinstance(value, dict):
            for op, operand in value.items():
                idx = len(params) + 1
                match op:
                    case "$gt":
                        params.append(operand)
                        parts.append(f'"{key}" > ${idx}')
                    case "$gte":
                        params.append(operand)
                        parts.append(f'"{key}" >= ${idx}')
                    case "$lt":
                        params.append(operand)
                        parts.append(f'"{key}" < ${idx}')
                    case "$lte":
                        params.append(operand)
                        parts.append(f'"{key}" <= ${idx}')
                    case "$in":
                        params.append(operand)
                        parts.append(f'"{key}" = ANY(${idx})')
                    case _:
                        raise ValueError(
                            f"Unsupported filter operator '{op}' on field '{key}'. "
                            "Supported: $gt, $gte, $lt, $lte, $in."
                        )
        else:
            idx = len(params) + 1
            params.append(value)
            parts.append(f'"{key}" = ${idx}')

    return " AND ".join(parts) if parts else "TRUE"


# ── Vector parsing ────────────────────────────────────────────────────────────

def _parse_vector(raw: Any) -> list[float]:
    """
    Convert whatever asyncpg returns for a vector column into list[float].

    asyncpg may return the pgvector type as a string '[0.1,0.2,...]',
    a numpy array (if pgvector codec is registered), or a list.
    """
    if isinstance(raw, (list, tuple)):
        return [float(x) for x in raw]
    if hasattr(raw, "tolist"):
        return raw.tolist()
    return [float(x) for x in str(raw).strip("[]").split(",")]


# ── Adapter ───────────────────────────────────────────────────────────────────

class PgvectorAdapter(VecDBAdapter):
    """
    pgvector implementation of VecDBAdapter.

    Uses an asyncpg connection pool. Connections are acquired per-operation
    and released immediately — never held for the adapter lifetime.
    """

    def __init__(self, config: PgvectorConfig) -> None:
        self._config = config
        self._pool: asyncpg.Pool | None = None
        self._distance_metric: str = "cosine"

    # ── Identity ──────────────────────────────────────────────────────────────

    @property
    def name(self) -> str:
        return self._config.name

    @property
    def backend_type(self) -> str:
        return "pgvector"

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def connect(self) -> None:
        self._pool = await asyncpg.create_pool(dsn=self._config.dsn)

        # Detect distance metric once at startup so queries use the right operator
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT indexdef FROM pg_indexes
                WHERE tablename = $1
                  AND indexdef ILIKE '%' || $2 || '%'
                """,
                self._config.table,
                self._config.vector_column,
            )
            self._distance_metric = _detect_metric(rows)

    async def disconnect(self) -> None:
        if self._pool is not None:
            await self._pool.close()
            self._pool = None

    # ── Internal ──────────────────────────────────────────────────────────────

    @property
    def _p(self) -> asyncpg.Pool:
        if self._pool is None:
            raise RuntimeError(
                f"PgvectorAdapter '{self.name}' is not connected. "
                "Call await adapter.connect() first."
            )
        return self._pool

    # ── Collections ───────────────────────────────────────────────────────────

    async def list_collections(self) -> list[CollectionInfo]:
        """pgvector is table-scoped — returns a single CollectionInfo for the configured table."""
        table = self._config.table
        vec_col = self._config.vector_column

        async with self._p.acquire() as conn:
            row_count: int = await conn.fetchval(f'SELECT COUNT(*) FROM "{table}"') or 0

            dim_row = await conn.fetchrow(
                """
                SELECT a.atttypmod
                FROM   pg_attribute a
                JOIN   pg_class c ON a.attrelid = c.oid
                WHERE  c.relname = $1 AND a.attname = $2
                """,
                table,
                vec_col,
            )
            # atttypmod stores the vector dimension directly for pgvector columns
            dimension = int(dim_row["atttypmod"]) if dim_row and dim_row["atttypmod"] > 0 else 0

        return [CollectionInfo(
            name=table,
            vector_count=row_count,
            dimension=dimension,
            distance_metric=self._distance_metric,
            backend_name=self.name,
        )]

    async def collection_stats(self, collection: str) -> CollectionStats:
        table = self._config.table
        vec_col = self._config.vector_column

        async with self._p.acquire() as conn:
            row_count: int = await conn.fetchval(f'SELECT COUNT(*) FROM "{table}"') or 0

            dim_row = await conn.fetchrow(
                """
                SELECT a.atttypmod
                FROM   pg_attribute a
                JOIN   pg_class c ON a.attrelid = c.oid
                WHERE  c.relname = $1 AND a.attname = $2
                """,
                table, vec_col,
            )
            dimension = int(dim_row["atttypmod"]) if dim_row and dim_row["atttypmod"] > 0 else 0

            index_rows = await conn.fetch(
                "SELECT indexname, indexdef FROM pg_indexes WHERE tablename = $1",
                table,
            )

            size_row = await conn.fetchrow(
                """
                SELECT
                    pg_total_relation_size($1::regclass) AS total_bytes,
                    pg_relation_size($1::regclass)       AS data_bytes
                """,
                table,
            )

        # Identify index type and params from indexdef
        index_type = "none"
        index_params: dict[str, Any] = {}
        for row in index_rows:
            idef = row["indexdef"].lower()
            if "hnsw" in idef:
                index_type = "hnsw"
                break
            if "ivfflat" in idef:
                index_type = "ivfflat"
                break

        return CollectionStats(
            name=table,
            backend_name=self.name,
            vector_count=row_count,
            dimension=dimension,
            distance_metric=self._distance_metric,
            disk_bytes=size_row["total_bytes"] if size_row else None,
            index_type=index_type,
            index_params=index_params,
            raw={
                "table": table,
                "indexes": [dict(r) for r in index_rows],
            },
        )

    # ── Query ─────────────────────────────────────────────────────────────────

    async def query(self, request: QueryRequest) -> QueryResult:
        table = self._config.table
        id_col = self._config.id_column
        vec_col = self._config.vector_column
        txt_col = self._config.text_column
        metric = self._distance_metric

        # $1 is always the query vector; asyncpg needs it as a string for pgvector
        vec_str = "[" + ",".join(str(x) for x in request.vector) + "]"
        filter_params: list[Any] = [vec_str]
        where = ""
        if request.filters:
            where_fragment = _build_where(request.filters, filter_params)
            where = f"WHERE {where_fragment}"

        limit = int(request.top_k)
        score = _score_expr(metric, vec_col)
        order = _order_expr(metric, vec_col)

        select_cols = f'"{id_col}", {score} AS score'
        if request.with_payload:
            select_cols += f', "{txt_col}"'
        if request.with_vectors:
            select_cols += f', "{vec_col}"::text AS _vec'

        sql = (
            f'SELECT {select_cols} '
            f'FROM "{table}" '
            f'{where} '
            f'ORDER BY {order} '
            f'LIMIT {limit}'
        )

        native_query: dict[str, Any] = {
            "sql": sql.replace(f"$1", f"[{len(request.vector)}-dim vector]"),
            "params": filter_params[1:],  # omit the vector itself
        }

        t0 = time.perf_counter()
        async with self._p.acquire() as conn:
            rows = await conn.fetch(sql, *filter_params)
        latency_ms = (time.perf_counter() - t0) * 1000

        hits: list[QueryHit] = []
        for row in rows:
            payload: dict[str, Any] = {}
            if request.with_payload and txt_col in row.keys():
                payload[txt_col] = row[txt_col]

            vector: list[float] | None = None
            if request.with_vectors and "_vec" in row.keys():
                vector = _parse_vector(row["_vec"])

            hits.append(QueryHit(
                id=str(row[id_col]),
                score=float(row["score"]),
                payload=payload,
                vector=vector,
            ))

        return QueryResult(
            hits=hits,
            total_hits=len(hits),
            backend_name=self.name,
            collection=table,
            latency_ms=round(latency_ms, 3),
            native_query=native_query,
        )

    # ── Vector fetch ──────────────────────────────────────────────────────────

    async def get_vectors(self, collection: str, ids: list[str]) -> list[VectorRecord]:
        table = self._config.table
        id_col = self._config.id_column
        vec_col = self._config.vector_column
        txt_col = self._config.text_column

        async with self._p.acquire() as conn:
            rows = await conn.fetch(
                f'SELECT "{id_col}", "{vec_col}"::text AS _vec, "{txt_col}" '
                f'FROM "{table}" '
                f'WHERE "{id_col}"::text = ANY($1)',
                ids,
            )

        return [
            VectorRecord(
                id=str(row[id_col]),
                vector=_parse_vector(row["_vec"]),
                payload={txt_col: row[txt_col]} if row[txt_col] else {},
                backend_name=self.name,
            )
            for row in rows
        ]

    # ── Health ────────────────────────────────────────────────────────────────

    async def health(self, collection: str) -> HealthReport:
        table = self._config.table
        vec_col = self._config.vector_column
        findings: list[HealthFinding] = []
        t0 = time.perf_counter()

        # ── 1. Reachability ───────────────────────────────────────────────────
        try:
            async with self._p.acquire() as conn:
                await conn.fetchval("SELECT 1")
        except Exception as exc:
            return HealthReport(
                backend_name=self.name,
                collection=table,
                status="unhealthy",
                findings=[HealthFinding(
                    severity="error",
                    code="unreachable",
                    message="Cannot connect to PostgreSQL.",
                    detail=str(exc),
                    recommendation="Check the DSN in vara.yaml and that PostgreSQL is running.",
                )],
                latency_ms=round((time.perf_counter() - t0) * 1000, 3),
            )

        async with self._p.acquire() as conn:
            # ── 2. pgvector extension installed? ──────────────────────────────
            ext = await conn.fetchrow(
                "SELECT extversion FROM pg_extension WHERE extname = 'vector'"
            )
            if not ext:
                findings.append(HealthFinding(
                    severity="error",
                    code="pgvector_not_installed",
                    message="pgvector extension is not installed in this database.",
                    detail="pg_extension WHERE extname='vector' returned no rows.",
                    recommendation="Run: CREATE EXTENSION IF NOT EXISTS vector;",
                ))

            # ── 3. Table exists? ──────────────────────────────────────────────
            table_exists: bool = await conn.fetchval(
                "SELECT EXISTS (SELECT FROM pg_tables WHERE tablename = $1)", table
            )
            if not table_exists:
                findings.append(HealthFinding(
                    severity="error",
                    code="table_not_found",
                    message=f"Table '{table}' does not exist.",
                    detail=f"tablename={table}",
                    recommendation="Check the 'table' field in vara.yaml.",
                ))
                return HealthReport(
                    backend_name=self.name,
                    collection=table,
                    status="unhealthy",
                    findings=findings,
                    latency_ms=round((time.perf_counter() - t0) * 1000, 3),
                )

            # ── 4. Vector index present? ──────────────────────────────────────
            index_rows = await conn.fetch(
                """
                SELECT indexname, indexdef FROM pg_indexes
                WHERE tablename = $1
                  AND indexdef ILIKE '%' || $2 || '%'
                """,
                table, vec_col,
            )
            has_hnsw    = any("hnsw"    in r["indexdef"].lower() for r in index_rows)
            has_ivfflat = any("ivfflat" in r["indexdef"].lower() for r in index_rows)

            if not has_hnsw and not has_ivfflat:
                findings.append(HealthFinding(
                    severity="warning",
                    code="no_vector_index",
                    message=f"No HNSW or IVFFlat index on column '{vec_col}'.",
                    detail=f"table={table}, column={vec_col}",
                    recommendation=(
                        f"Create an HNSW index:\n"
                        f"  CREATE INDEX ON {table} "
                        f"USING hnsw ({vec_col} vector_cosine_ops);"
                    ),
                ))

            # ── 5. Empty table? ───────────────────────────────────────────────
            row_count: int = await conn.fetchval(f'SELECT COUNT(*) FROM "{table}"') or 0
            if row_count == 0:
                findings.append(HealthFinding(
                    severity="warning",
                    code="empty_table",
                    message=f"Table '{table}' contains no rows.",
                    detail="COUNT(*)=0",
                    recommendation="Insert data before running queries.",
                ))

        try:
            stats = await self.collection_stats(table)
        except Exception:
            stats = None

        severities = {f.severity for f in findings}
        status = "unhealthy" if "error" in severities else (
            "degraded" if "warning" in severities else "healthy"
        )

        return HealthReport(
            backend_name=self.name,
            collection=table,
            status=status,
            findings=findings,
            stats=stats,
            latency_ms=round((time.perf_counter() - t0) * 1000, 3),
        )


__all__ = ["PgvectorAdapter"]
