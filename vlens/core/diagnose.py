"""
Retrieval diagnosis helpers.

This module explains why expected documents did or did not appear in a vector
search result. The first pass is intentionally heuristic and adapter-agnostic:
it uses query rank/score, optional filter context, and direct vector lookup.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from vlens.adapters.base import QueryHit, VecDBAdapter, VectorRecord
from vlens.core.debug import debug_query
from vlens.core.rules import (
    DEFAULT_DIAGNOSIS_TOP_K,
    DIAGNOSIS_EXPECTED_ID_MULTIPLIER,
    EXPECTED_DOCUMENT_LOW_RANK,
    EXPECTED_DOCUMENT_NOT_FOUND,
    EXPECTED_DOCUMENT_NOT_RETRIEVED,
    EXPECTED_DOCUMENT_RETRIEVED,
    LOW_RANK_FRACTION,
    LOW_SCORE_GAP_FRACTION,
    POSSIBLE_EMBEDDING_MISMATCH,
    POSSIBLE_FILTER_EXCLUSION,
    POSSIBLE_INDEX_RECALL_ISSUE,
    SEVERITY_ERROR,
    SEVERITY_INFO,
    SEVERITY_WARNING,
)


class DiagnosisFinding(BaseModel):
    """One explanation or observation produced during retrieval diagnosis."""

    severity: str
    code: str
    message: str
    detail: str = ""
    recommendation: str = ""


class ExpectedDocumentDiagnosis(BaseModel):
    """Diagnosis for one expected document ID."""

    id: str
    found: bool
    retrieved: bool
    rank: int | None = None
    score: float | None = None
    score_gap_to_top: float | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    findings: list[DiagnosisFinding] = Field(default_factory=list)


class DiagnosisResult(BaseModel):
    """Structured retrieval diagnosis for one backend and query."""

    backend_name: str
    backend_type: str
    collection: str
    top_k: int
    expected_ids: list[str]
    retrieved_ids: list[str]
    native_query: dict[str, Any] = Field(default_factory=dict)
    errors: list[str] = Field(default_factory=list)
    document_diagnoses: list[ExpectedDocumentDiagnosis] = Field(default_factory=list)
    summary: str
    verdict: str | None = None
    hit_count: int = 0
    total_expected: int = 0
    recall_at_k: float | None = None
    mrr: float | None = None


async def diagnose_retrieval(
    query_vector: list[float],
    collection: str,
    backend: VecDBAdapter,
    expected_ids: list[str],
    *,
    top_k: int | None = None,
    filters: dict[str, Any] | None = None,
) -> DiagnosisResult:
    """
    Diagnose why expected documents were or were not retrieved.

    Args:
        query_vector: Query embedding.
        collection: Collection/index name to query.
        backend: Connected vector DB adapter.
        expected_ids: Document IDs that should ideally be present in results.
        top_k: Query depth. Defaults to max(50, len(expected_ids) * 5).
        filters: Optional Vector Lens canonical filter dictionary.

    Returns:
        DiagnosisResult with per-document findings and a human-readable summary.
    """
    effective_top_k = top_k or max(
        DEFAULT_DIAGNOSIS_TOP_K,
        len(expected_ids) * DIAGNOSIS_EXPECTED_ID_MULTIPLIER,
    )

    debug = await debug_query(
        query_vector,
        collection,
        [backend],
        top_k=effective_top_k,
        filters=filters,
        with_payload=True,
        with_vectors=False,
    )

    query_result = debug.results[0] if debug.results else None
    query_errors = [error.error for error in debug.errors]
    hits = query_result.hits if query_result else []
    retrieved_ids = [hit.id for hit in hits]
    native_query = query_result.native_query if query_result else {}
    records_by_id = await _fetch_expected_records(backend, collection, expected_ids)

    top_score = hits[0].score if hits else None
    diagnoses = [
        _diagnose_expected_id(
            expected_id=expected_id,
            hits=hits,
            records_by_id=records_by_id,
            top_score=top_score,
            top_k=effective_top_k,
            filters=filters,
        )
        for expected_id in expected_ids
    ]

    total_expected = len(expected_ids)
    hit_count = sum(1 for d in diagnoses if d.retrieved)
    recall_at_k = hit_count / total_expected if total_expected > 0 else None
    mrr = (
        sum(1.0 / d.rank for d in diagnoses if d.retrieved and d.rank is not None) / total_expected
        if total_expected > 0
        else None
    )

    return DiagnosisResult(
        backend_name=backend.name,
        backend_type=backend.backend_type,
        collection=collection,
        top_k=effective_top_k,
        expected_ids=expected_ids,
        retrieved_ids=retrieved_ids,
        native_query=native_query,
        errors=query_errors,
        document_diagnoses=diagnoses,
        summary=_summarize(diagnoses, query_errors),
        verdict=_classify_verdict(diagnoses, query_errors),
        hit_count=hit_count,
        total_expected=total_expected,
        recall_at_k=recall_at_k,
        mrr=mrr,
    )


async def _fetch_expected_records(
    backend: VecDBAdapter,
    collection: str,
    expected_ids: list[str],
) -> dict[str, VectorRecord]:
    if not expected_ids:
        return {}

    try:
        records = await backend.get_vectors(collection, expected_ids)
    except Exception:
        return {}

    return {record.id: record for record in records}


def _diagnose_expected_id(
    *,
    expected_id: str,
    hits: list[QueryHit],
    records_by_id: dict[str, VectorRecord],
    top_score: float | None,
    top_k: int,
    filters: dict[str, Any] | None,
) -> ExpectedDocumentDiagnosis:
    hit_by_id = {hit.id: hit for hit in hits}
    ranks = {hit.id: rank for rank, hit in enumerate(hits, start=1)}
    hit = hit_by_id.get(expected_id)
    record = records_by_id.get(expected_id)
    findings: list[DiagnosisFinding] = []

    if hit is not None:
        rank = ranks[expected_id]
        score_gap = _score_gap(top_score, hit.score)
        findings.append(_retrieved_finding(expected_id, rank, hit.score))

        if _is_low_rank(rank, top_k) or _has_large_score_gap(score_gap, top_score):
            findings.append(_low_rank_finding(expected_id, rank, top_k, score_gap))

        return ExpectedDocumentDiagnosis(
            id=expected_id,
            found=True,
            retrieved=True,
            rank=rank,
            score=hit.score,
            score_gap_to_top=score_gap,
            payload=hit.payload,
            findings=findings,
        )

    if record is None:
        findings.append(
            DiagnosisFinding(
                severity=SEVERITY_ERROR,
                code=EXPECTED_DOCUMENT_NOT_FOUND,
                message=f"Expected document '{expected_id}' was not found by ID lookup.",
                detail="adapter.get_vectors returned no record for this ID",
                recommendation=(
                    "Verify the document ID, collection name, and whether the document "
                    "was inserted into this backend."
                ),
            )
        )

        return ExpectedDocumentDiagnosis(
            id=expected_id,
            found=False,
            retrieved=False,
            findings=findings,
        )

    findings.append(
        DiagnosisFinding(
            severity=SEVERITY_WARNING,
            code=EXPECTED_DOCUMENT_NOT_RETRIEVED,
            message=f"Expected document '{expected_id}' exists but was not in the top {top_k}.",
            detail="document exists by ID lookup but did not appear in query results",
            recommendation=(
                "Inspect the embedding for this document and compare it with the query. "
                "If approximate search is enabled, also review index recall settings."
            ),
        )
    )

    if filters:
        findings.append(
            DiagnosisFinding(
                severity=SEVERITY_WARNING,
                code=POSSIBLE_FILTER_EXCLUSION,
                message="Filters may be excluding this expected document.",
                detail=f"filters={filters}",
                recommendation=(
                    "Compare the document payload with the query filter and inspect the "
                    "adapter native_query translation."
                ),
            )
        )
    else:
        findings.append(
            DiagnosisFinding(
                severity=SEVERITY_INFO,
                code=POSSIBLE_EMBEDDING_MISMATCH,
                message="The document may be embedded far from the query.",
                detail="no filter was applied, so ranking is likely driven by vector distance",
                recommendation=(
                    "Check chunk text, embedding model version, normalization, and whether "
                    "query/document embeddings were produced by the same model."
                ),
            )
        )
        findings.append(
            DiagnosisFinding(
                severity=SEVERITY_INFO,
                code=POSSIBLE_INDEX_RECALL_ISSUE,
                message="Approximate index recall could also be a factor.",
                detail="document exists but was absent from the inspected result window",
                recommendation=(
                    "Run a deeper top_k query or compare against exact search if the "
                    "backend supports it."
                ),
            )
        )

    return ExpectedDocumentDiagnosis(
        id=expected_id,
        found=True,
        retrieved=False,
        payload=record.payload,
        findings=findings,
    )


def _retrieved_finding(expected_id: str, rank: int, score: float) -> DiagnosisFinding:
    return DiagnosisFinding(
        severity=SEVERITY_INFO,
        code=EXPECTED_DOCUMENT_RETRIEVED,
        message=f"Expected document '{expected_id}' was retrieved at rank {rank}.",
        detail=f"rank={rank}, score={score}",
    )


def _low_rank_finding(
    expected_id: str,
    rank: int,
    top_k: int,
    score_gap: float | None,
) -> DiagnosisFinding:
    detail = f"rank={rank}, top_k={top_k}"
    if score_gap is not None:
        detail = f"{detail}, score_gap_to_top={score_gap}"

    return DiagnosisFinding(
        severity=SEVERITY_WARNING,
        code=EXPECTED_DOCUMENT_LOW_RANK,
        message=f"Expected document '{expected_id}' was retrieved, but at a low rank.",
        detail=detail,
        recommendation=(
            "Inspect chunk quality and embedding similarity. A relevant document near "
            "the bottom of top_k may indicate weak semantic match or noisy chunks."
        ),
    )


def _is_low_rank(rank: int, top_k: int) -> bool:
    return rank > max(1, int(top_k * LOW_RANK_FRACTION))


def _has_large_score_gap(score_gap: float | None, top_score: float | None) -> bool:
    if score_gap is None or top_score is None or top_score == 0:
        return False
    return abs(score_gap / top_score) >= LOW_SCORE_GAP_FRACTION


def _score_gap(top_score: float | None, score: float) -> float | None:
    if top_score is None:
        return None
    return round(top_score - score, 6)


def _classify_verdict(
    diagnoses: list[ExpectedDocumentDiagnosis],
    errors: list[str],
) -> str | None:
    if errors or not diagnoses:
        return None
    if all(d.retrieved for d in diagnoses):
        return None

    not_found = 0
    filter_issue = 0
    embedding_issue = 0
    low_rank = 0

    for d in diagnoses:
        codes = {f.code for f in d.findings}
        if not d.found:
            not_found += 1
        elif not d.retrieved and POSSIBLE_FILTER_EXCLUSION in codes:
            filter_issue += 1
        elif not d.retrieved:
            embedding_issue += 1
        elif d.retrieved and EXPECTED_DOCUMENT_LOW_RANK in codes:
            low_rank += 1

    tally: list[tuple[int, str]] = [
        (
            not_found,
            "Most likely: documents not in index — verify IDs, collection name, and whether data was inserted.",
        ),
        (
            filter_issue,
            "Most likely: active filter is excluding expected documents — inspect payload values and the native_query filter translation.",
        ),
        (
            embedding_issue,
            "Most likely: embedding mismatch or index recall too low — check embedding model version, normalization, and consider increasing top_k.",
        ),
        (
            low_rank,
            "Most likely: weak semantic match — expected documents were retrieved but ranked low. Inspect chunk quality and embedding similarity.",
        ),
    ]
    tally.sort(key=lambda t: t[0], reverse=True)

    count, verdict = tally[0]
    return verdict if count > 0 else None


def _summarize(diagnoses: list[ExpectedDocumentDiagnosis], errors: list[str]) -> str:
    if errors:
        return f"Query failed on the backend: {errors[0]}"

    total = len(diagnoses)
    retrieved = sum(1 for diagnosis in diagnoses if diagnosis.retrieved)
    found = sum(1 for diagnosis in diagnoses if diagnosis.found)
    missing = total - found

    if total == 0:
        return "No expected document IDs were provided."
    if retrieved == total:
        return f"All {total} expected document(s) were retrieved."
    if missing:
        return (
            f"{retrieved}/{total} expected document(s) were retrieved; "
            f"{missing} expected ID(s) were not found in the collection."
        )
    return (
        f"{retrieved}/{total} expected document(s) were retrieved; "
        "the remaining expected documents exist but were outside the inspected result window."
    )


__all__ = [
    "DiagnosisFinding",
    "DiagnosisResult",
    "ExpectedDocumentDiagnosis",
    "diagnose_retrieval",
]
