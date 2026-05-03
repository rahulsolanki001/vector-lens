"""
vara.config — Configuration loading and validation.

Public API:
    load_config(path)              → VaraConfig
    resolve_adapter_config(backend) → AdapterConfig
    get_adapter_configs(config)     → list[AdapterConfig]

Usage:
    from vara.config import load_config, get_adapter_configs

    config = load_config("vara.yaml")
    adapters = get_adapter_configs(config)
"""

from vara.config.loader import get_adapter_configs, load_config, resolve_adapter_config
from vara.config.schema import BackendConfig, VaraConfig, VaraSettings

__all__ = [
    "BackendConfig",
    "VaraConfig",
    "VaraSettings",
    "get_adapter_configs",
    "load_config",
    "resolve_adapter_config",
]
