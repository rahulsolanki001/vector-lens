"""
Shared pytest fixtures.
"""

from __future__ import annotations

import pytest


@pytest.fixture
def sample_vector() -> list[float]:
    return [0.1, 0.2, 0.3]


@pytest.fixture
def sample_vectors() -> list[list[float]]:
    return [
        [0.1, 0.2, 0.3],
        [0.2, 0.1, 0.4],
        [0.9, 0.1, 0.1],
    ]
