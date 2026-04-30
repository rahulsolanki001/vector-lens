"""
Evaluation harness.

Phase 3 will expose retrieval metrics, dataset loaders, an embedding cache, and
an async eval runner from this package.
"""

from vara.eval.cache import EmbeddingCache
from vara.eval.loaders import BEIRLoader, CSVLoader, EvalDataset, EvalQuery, FiQALoader
from vara.eval.metrics import latency_percentiles, mrr_at_k, ndcg_at_k, recall_at_k
from vara.eval.runner import EvalProgress, run_eval

__all__ = [
    "BEIRLoader",
    "CSVLoader",
    "EmbeddingCache",
    "EvalDataset",
    "EvalProgress",
    "EvalQuery",
    "FiQALoader",
    "latency_percentiles",
    "mrr_at_k",
    "ndcg_at_k",
    "recall_at_k",
    "run_eval",
]
