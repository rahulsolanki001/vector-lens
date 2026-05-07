"""
Collection sampler for the eval harness.

Builds an EvalDataset directly from a live adapter by fetching N random vectors
from the collection.  Each sampled vector becomes a query whose only relevant
document is itself — a self-retrieval sanity check: rank-1 recall of 1.0
means the index can always find its own vectors.
"""

from __future__ import annotations

import random

from vlens.adapters.base import VecDBAdapter
from vlens.eval.loaders import EvalDataset, EvalQuery


async def sample_collection(
    adapter: VecDBAdapter,
    collection: str,
    n_samples: int,
    *,
    seed: int | None = None,
) -> EvalDataset:
    """
    Sample ``n_samples`` vectors from ``collection`` and wrap them as an
    EvalDataset for self-retrieval eval.

    Each EvalQuery has:
      - id:           the point's own ID
      - text:         empty string (not used for vector search)
      - vector:       the stored embedding
      - relevant_ids: {id}  — the point itself is the only relevant document

    Args:
        adapter:    Connected adapter to sample from.
        collection: Collection / index name.
        n_samples:  Number of vectors to sample.
        seed:       Optional RNG seed for reproducibility.
    """
    stats = await adapter.collection_stats(collection)
    total = stats.vector_count

    if total == 0:
        raise ValueError(f"Collection '{collection}' is empty.")

    n = min(n_samples, total)

    # Build a candidate ID range.  Adapters expose integer or string IDs; we
    # request a slightly larger pool then trim so we still get n even if some
    # IDs are gaps (deleted points).
    pool_size = min(int(n * 1.5) + 10, total)
    rng = random.Random(seed)
    candidate_ids = [str(i) for i in rng.sample(range(total), min(pool_size, total))]

    records = await adapter.get_vectors(collection, candidate_ids)
    if not records:
        raise ValueError(f"Adapter returned no vectors for the sampled IDs from '{collection}'.")

    # Trim to exactly n (get_vectors may return fewer if IDs are non-sequential)
    records = records[:n]

    queries = [
        EvalQuery(
            id=r.id,
            text="",
            vector=r.vector,
            relevant_ids={r.id},
            metadata=r.payload,
        )
        for r in records
        if r.vector
    ]

    if not queries:
        raise ValueError("No vectors with embeddings found in the sampled records.")

    return EvalDataset(
        name=f"{collection}_sample_{len(queries)}",
        queries=queries,
        metadata={
            "source": "collection",
            "collection": collection,
            "n_samples": len(queries),
            "total_vectors": total,
        },
    )


__all__ = ["sample_collection"]
