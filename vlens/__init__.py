"""
Vector Lens — Vector database debugger and visualizer.

Public SDK surface. Import from here in your RAG pipeline:

    from vlens import debug_query, health_check, diagnose_retrieval, compare_backends
"""

from vlens.core.debug import compare_backends, debug_query
from vlens.core.diagnose import diagnose_retrieval
from vlens.core.health import health_check

__version__ = "0.1.0"
__all__ = [
    "compare_backends",
    "debug_query",
    "diagnose_retrieval",
    "health_check",
]
