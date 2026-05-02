"""HDBSCAN clustering on projected coordinates (uses scikit-learn >= 1.3)."""
from __future__ import annotations

import numpy as np

from vara.projection.jobs import ProjectionPoint


def run_hdbscan(
    points: list[ProjectionPoint],
    min_cluster_size: int = 5,
    min_samples: int | None = None,
) -> dict[str, int]:
    """
    Cluster projected points using HDBSCAN.

    Operates on the x/y/z coordinates already in the job store — no re-projection.
    Returns a mapping of point ID → cluster label.  Label -1 means noise.
    """
    try:
        from sklearn.cluster import HDBSCAN
    except ImportError as exc:
        raise ImportError(
            "scikit-learn>=1.3 is required for clustering.\n"
            "Install it with: pip install vara[viz]"
        ) from exc

    if len(points) < 2:
        return {p.id: 0 for p in points}

    coords = np.array([[p.x, p.y, p.z] for p in points], dtype=np.float32)

    # Clamp to valid range — must be ≥ 2 and ≤ n_samples
    mcs = max(2, min(min_cluster_size, len(points) - 1))

    clusterer = HDBSCAN(min_cluster_size=mcs, min_samples=min_samples)
    labels: np.ndarray = clusterer.fit_predict(coords)

    return {p.id: int(labels[i]) for i, p in enumerate(points)}


__all__ = ["run_hdbscan"]
