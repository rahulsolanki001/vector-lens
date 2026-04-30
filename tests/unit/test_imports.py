"""
Smoke tests for the public import surface.
"""

from __future__ import annotations

import pytest


@pytest.mark.unit
def test_public_sdk_imports() -> None:
    import vara

    assert vara.__version__ == "0.1.0"
    assert callable(vara.debug_query)
    assert callable(vara.compare_backends)
    assert callable(vara.health_check)
    assert callable(vara.diagnose_retrieval)


@pytest.mark.unit
def test_core_imports() -> None:
    from vara.core import compare_backends, debug_query, diagnose_retrieval, health_check

    assert callable(debug_query)
    assert callable(compare_backends)
    assert callable(health_check)
    assert callable(diagnose_retrieval)


@pytest.mark.unit
def test_config_imports() -> None:
    from vara.config import BackendConfig, VaraConfig, VaraSettings

    config = VaraConfig(vara=VaraSettings(), backends=[
        BackendConfig(name="local-qdrant", type="qdrant")
    ])

    assert config.backend_names == ["local-qdrant"]


@pytest.mark.unit
def test_adapter_registry_import() -> None:
    from vara.adapters import build_adapter

    assert callable(build_adapter)


@pytest.mark.unit
def test_eval_projection_server_imports() -> None:
    import vara.eval
    import vara.projection
    import vara.server

    assert vara.eval.__all__
    assert vara.projection.__all__
    assert callable(vara.server.create_app)
