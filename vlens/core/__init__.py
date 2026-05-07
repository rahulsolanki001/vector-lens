"""
Core debugging primitives for Vector Lens.

This package owns the backend-agnostic logic that sits between adapters and
user-facing entry points such as the CLI, API server, and public SDK imports.

Planned modules:
    debug      Query debugging and backend comparison helpers.
    health     Collection/backend health checks.
    diagnose   Retrieval failure diagnosis.
    rules      Shared finding codes and diagnostic rules.
"""

from vlens.core.debug import compare_backends, debug_query
from vlens.core.diagnose import diagnose_retrieval
from vlens.core.health import health_check

__all__ = [
    "compare_backends",
    "debug_query",
    "diagnose_retrieval",
    "health_check",
]
