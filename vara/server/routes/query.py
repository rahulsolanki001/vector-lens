"""
Query debugger routes.

POST /api/query/debug    — fan out a query across one or more backends
POST /api/query/compare  — side-by-side diff of two backends
POST /api/query/diagnose — explain why expected docs are missing or low-ranked
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from vara.adapters.base import VecDBAdapter
from vara.core.debug import BackendComparison, DebugQueryResult, compare_backends, debug_query
from vara.core.diagnose import DiagnosisResult, diagnose_retrieval
from vara.server.deps import get_adapters, require_adapter

router = APIRouter(prefix="/query", tags=["query"])


# ── Request models ────────────────────────────────────────────────────────────


class DebugQueryRequest(BaseModel):
    vector: list[float]
    collection: str
    backend_names: list[str] | None = None  # None → all backends
    top_k: int = Field(default=10, ge=1, le=1000)
    filters: dict[str, Any] | None = None
    with_payload: bool = True
    with_vectors: bool = False


class CompareRequest(BaseModel):
    vector: list[float]
    collection: str
    backend_a: str
    backend_b: str
    top_k: int = Field(default=10, ge=1, le=1000)
    filters: dict[str, Any] | None = None


class DiagnoseRequest(BaseModel):
    vector: list[float]
    collection: str
    backend_name: str
    expected_ids: list[str] = Field(min_length=1)
    filters: dict[str, Any] | None = None


# ── Routes ────────────────────────────────────────────────────────────────────


@router.post("/debug", response_model=DebugQueryResult)
async def debug_query_route(
    body: DebugQueryRequest,
    adapters: dict[str, VecDBAdapter] = Depends(get_adapters),
) -> DebugQueryResult:
    """Run a vector search across one or more backends and return aligned results."""
    if body.backend_names is not None:
        backends = [require_adapter(name, adapters) for name in body.backend_names]
    else:
        backends = list(adapters.values())

    if not backends:
        raise HTTPException(status_code=400, detail="No backends available to query.")

    return await debug_query(
        body.vector,
        body.collection,
        backends,
        top_k=body.top_k,
        filters=body.filters,
        with_payload=body.with_payload,
        with_vectors=body.with_vectors,
    )


@router.post("/compare", response_model=BackendComparison)
async def compare_backends_route(
    body: CompareRequest,
    adapters: dict[str, VecDBAdapter] = Depends(get_adapters),
) -> BackendComparison:
    """Compare the same query across two backends with Jaccard and Spearman metrics."""
    adapter_a = require_adapter(body.backend_a, adapters)
    adapter_b = require_adapter(body.backend_b, adapters)

    if body.backend_a == body.backend_b:
        raise HTTPException(
            status_code=400,
            detail="backend_a and backend_b must be different.",
        )

    return await compare_backends(
        body.vector,
        body.collection,
        adapter_a,
        adapter_b,
        top_k=body.top_k,
        filters=body.filters,
    )


@router.post("/diagnose", response_model=DiagnosisResult)
async def diagnose_query_route(
    body: DiagnoseRequest,
    adapters: dict[str, VecDBAdapter] = Depends(get_adapters),
) -> DiagnosisResult:
    """Diagnose why expected documents are missing or low-ranked in results."""
    adapter = require_adapter(body.backend_name, adapters)
    return await diagnose_retrieval(
        body.vector,
        body.collection,
        adapter,
        body.expected_ids,
        filters=body.filters,
    )


__all__ = ["router"]
