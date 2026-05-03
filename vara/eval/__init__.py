"""
Evaluation harness.

Phase 3 will expose retrieval metrics, dataset loaders, an embedding cache, and
an async eval runner from this package.
"""

from vara.eval.cache import EmbeddingCache
from vara.eval.loaders import CSVLoader, EvalDataset, EvalQuery, FiQALoader, JSONLoader
from vara.eval.metrics import latency_percentiles, mrr_at_k, ndcg_at_k, recall_at_k
from vara.eval.runner import EvalProgress, run_eval
from vara.eval.sampler import sample_collection

__all__ = [
    "CSVLoader",
    "EmbeddingCache",
    "EvalDataset",
    "EvalProgress",
    "EvalQuery",
    "FiQALoader",
    "JSONLoader",
    "latency_percentiles",
    "mrr_at_k",
    "ndcg_at_k",
    "recall_at_k",
    "run_eval",
    "sample_collection",
]
