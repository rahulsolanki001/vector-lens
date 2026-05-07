"""
Shared diagnostic rule codes and thresholds.

Rules live in core so every adapter can report comparable finding codes. Adapter
implementations still own DB-specific inspection, while this module owns the
stable vocabulary used by the SDK, CLI, API, and UI.
"""

from __future__ import annotations

from typing import Final

from vlens.adapters.base import HealthFinding

# Severity levels
SEVERITY_ERROR: Final = "error"
SEVERITY_WARNING: Final = "warning"
SEVERITY_INFO: Final = "info"

VALID_SEVERITIES: Final = frozenset(
    {
        SEVERITY_ERROR,
        SEVERITY_WARNING,
        SEVERITY_INFO,
    }
)


# Health statuses
STATUS_HEALTHY: Final = "healthy"
STATUS_DEGRADED: Final = "degraded"
STATUS_UNHEALTHY: Final = "unhealthy"


# Adapter/core health rule codes
UNREACHABLE: Final = "unreachable"
COLLECTION_NOT_FOUND: Final = "collection_not_found"
COLLECTION_STATUS_GREY: Final = "collection_status_grey"
COLLECTION_STATUS_UNHEALTHY: Final = "collection_status_unhealthy"
HNSW_EF_CONSTRUCT_TOO_LOW: Final = "hnsw_ef_construct_too_low"
HNSW_EF_CONSTRUCT_MARGINAL: Final = "hnsw_ef_construct_marginal"
HNSW_M_TOO_LOW: Final = "hnsw_m_too_low"
HIGH_SEGMENT_COUNT: Final = "high_segment_count"
INDEXING_LAG: Final = "indexing_lag"
NO_PAYLOAD_INDEXES: Final = "no_payload_indexes"


# Retrieval diagnosis rule codes
EXPECTED_DOCUMENT_RETRIEVED: Final = "expected_document_retrieved"
EXPECTED_DOCUMENT_LOW_RANK: Final = "expected_document_low_rank"
EXPECTED_DOCUMENT_NOT_RETRIEVED: Final = "expected_document_not_retrieved"
EXPECTED_DOCUMENT_NOT_FOUND: Final = "expected_document_not_found"
POSSIBLE_FILTER_EXCLUSION: Final = "possible_filter_exclusion"
POSSIBLE_EMBEDDING_MISMATCH: Final = "possible_embedding_mismatch"
POSSIBLE_INDEX_RECALL_ISSUE: Final = "possible_index_recall_issue"


# Cross-backend/query thresholds
DEFAULT_DIAGNOSIS_TOP_K: Final = 50
DIAGNOSIS_EXPECTED_ID_MULTIPLIER: Final = 5
LOW_RANK_FRACTION: Final = 0.5
LOW_SCORE_GAP_FRACTION: Final = 0.25


# Index health thresholds shared by adapters.
MIN_HNSW_EF_CONSTRUCT: Final = 64
RECOMMENDED_LARGE_COLLECTION_EF_CONSTRUCT: Final = 128
LARGE_COLLECTION_VECTOR_COUNT: Final = 100_000
MIN_HNSW_M: Final = 8
HIGH_SEGMENT_COUNT_THRESHOLD: Final = 20
INDEXING_LAG_WARNING_PCT: Final = 10.0


def make_finding(
    *,
    severity: str,
    code: str,
    message: str,
    detail: str = "",
    recommendation: str = "",
) -> HealthFinding:
    """Create a HealthFinding after validating the shared severity vocabulary."""
    if severity not in VALID_SEVERITIES:
        raise ValueError(
            f"Unknown severity '{severity}'. Valid severities: {sorted(VALID_SEVERITIES)}."
        )

    return HealthFinding(
        severity=severity,
        code=code,
        message=message,
        detail=detail,
        recommendation=recommendation,
    )


def status_from_findings(findings: list[HealthFinding]) -> str:
    """Collapse finding severities into a report status."""
    severities = {finding.severity for finding in findings}

    if SEVERITY_ERROR in severities:
        return STATUS_UNHEALTHY
    if SEVERITY_WARNING in severities:
        return STATUS_DEGRADED
    return STATUS_HEALTHY


__all__ = [
    "COLLECTION_NOT_FOUND",
    "COLLECTION_STATUS_GREY",
    "COLLECTION_STATUS_UNHEALTHY",
    "DEFAULT_DIAGNOSIS_TOP_K",
    "DIAGNOSIS_EXPECTED_ID_MULTIPLIER",
    "EXPECTED_DOCUMENT_LOW_RANK",
    "EXPECTED_DOCUMENT_NOT_FOUND",
    "EXPECTED_DOCUMENT_NOT_RETRIEVED",
    "EXPECTED_DOCUMENT_RETRIEVED",
    "HIGH_SEGMENT_COUNT",
    "HIGH_SEGMENT_COUNT_THRESHOLD",
    "HNSW_EF_CONSTRUCT_MARGINAL",
    "HNSW_EF_CONSTRUCT_TOO_LOW",
    "HNSW_M_TOO_LOW",
    "INDEXING_LAG",
    "INDEXING_LAG_WARNING_PCT",
    "LARGE_COLLECTION_VECTOR_COUNT",
    "LOW_RANK_FRACTION",
    "LOW_SCORE_GAP_FRACTION",
    "MIN_HNSW_EF_CONSTRUCT",
    "MIN_HNSW_M",
    "NO_PAYLOAD_INDEXES",
    "POSSIBLE_EMBEDDING_MISMATCH",
    "POSSIBLE_FILTER_EXCLUSION",
    "POSSIBLE_INDEX_RECALL_ISSUE",
    "RECOMMENDED_LARGE_COLLECTION_EF_CONSTRUCT",
    "SEVERITY_ERROR",
    "SEVERITY_INFO",
    "SEVERITY_WARNING",
    "STATUS_DEGRADED",
    "STATUS_HEALTHY",
    "STATUS_UNHEALTHY",
    "UNREACHABLE",
    "VALID_SEVERITIES",
    "make_finding",
    "status_from_findings",
]
