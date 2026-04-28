"""
Core debugging primitives for Vara.

This package owns the backend-agnostic logic that sits between adapters and
user-facing entry points such as the CLI, API server, and public SDK imports.

Planned modules:
    debug      Query debugging and backend comparison helpers.
    health     Collection/backend health checks.
    diagnose   Retrieval failure diagnosis.
    rules      Shared finding codes and diagnostic rules.
"""

from vara.core.debug import compare_backends, debug_query
from vara.core.diagnose import diagnose_retrieval
from vara.core.health import health_check

__all__ = [
    "debug_query",
    "compare_backends",
    "health_check",
    "diagnose_retrieval",
]
