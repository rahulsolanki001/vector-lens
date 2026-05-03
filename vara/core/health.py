"""
Backend-agnostic health checks.

Adapters own database-specific inspection. This module provides the stable core
entry point used by the SDK, CLI, API server, and tests.
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence

from pydantic import BaseModel, Field

from vara.adapters.base import HealthReport, VecDBAdapter
from vara.core.rules import status_from_findings


class HealthCheckSummary(BaseModel):
    """Aggregated health result across one collection and multiple backends."""

    collection: str
    status: str
    reports: list[HealthReport] = Field(default_factory=list)


async def health_check(adapter: VecDBAdapter, collection: str) -> HealthReport:
    """
    Run a health check for one backend collection.

    The adapter returns the concrete report. Core normalizes the status from the
    finding severities so all adapters follow the same status semantics.
    """
    report = await adapter.health(collection)
    normalized_status = status_from_findings(report.findings)

    if report.status != normalized_status:
        return report.model_copy(update={"status": normalized_status})

    return report


async def health_check_many(
    adapters: Sequence[VecDBAdapter],
    collection: str,
) -> HealthCheckSummary:
    """
    Run health checks for the same collection across multiple backends.

    This helper is useful for the CLI and server routes that need a compact
    overall status while still preserving each adapter's full report.
    """
    reports = await asyncio.gather(*(health_check(adapter, collection) for adapter in adapters))
    all_findings = [finding for report in reports for finding in report.findings]

    return HealthCheckSummary(
        collection=collection,
        status=status_from_findings(all_findings),
        reports=reports,
    )


__all__ = [
    "HealthCheckSummary",
    "HealthReport",
    "health_check",
    "health_check_many",
]
