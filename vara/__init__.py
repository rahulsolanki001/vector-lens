"""
Vara — Vector database debugger and visualizer.

Public SDK surface. Import from here in your RAG pipeline:

    from vara import debug_query, health_check, diagnose_retrieval, compare_backends
"""

from vara.core.debug import compare_backends, debug_query
from vara.core.diagnose import diagnose_retrieval
from vara.core.health import health_check

__version__ = "0.1.0"
__all__ = [
    "compare_backends",
    "debug_query",
    "diagnose_retrieval",
    "health_check",
]
