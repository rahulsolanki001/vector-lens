"""
Smoke tests for the public import surface.
"""

from __future__ import annotations

import pytest


@pytest.mark.unit
def test_public_sdk_imports() -> None:
    import vlens

    assert vlens.__version__ == "0.1.0"
    assert callable(vlens.debug_query)
    assert callable(vlens.compare_backends)
    assert callable(vlens.health_check)
    assert callable(vlens.diagnose_retrieval)


@pytest.mark.unit
def test_core_imports() -> None:
    from vlens.core import compare_backends, debug_query, diagnose_retrieval, health_check

    assert callable(debug_query)
    assert callable(compare_backends)
    assert callable(health_check)
    assert callable(diagnose_retrieval)


@pytest.mark.unit
def test_config_imports() -> None:
    from vlens.config import BackendConfig, VlensConfig

    config = VlensConfig(
        backends=[BackendConfig(name="local-qdrant", type="qdrant")]
    )

    assert config.backend_names == ["local-qdrant"]


@pytest.mark.unit
def test_adapter_registry_import() -> None:
    from vlens.adapters import build_adapter

    assert callable(build_adapter)


@pytest.mark.unit
def test_eval_projection_server_imports() -> None:
    import vlens.eval
    import vlens.projection
    import vlens.server

    assert vlens.eval.__all__
    assert vlens.projection.__all__
    assert callable(vlens.server.create_app)
