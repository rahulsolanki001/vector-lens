"""
vlens.config — Configuration loading and validation.

Public API:
    load_config(path)              → VlensConfig
    resolve_adapter_config(backend) → AdapterConfig
    get_adapter_configs(config)     → list[AdapterConfig]

Usage:
    from vlens.config import load_config, get_adapter_configs

    config = load_config("vlens.yaml")
    adapters = get_adapter_configs(config)
"""

from vlens.config.loader import get_adapter_configs, load_config, resolve_adapter_config
from vlens.config.schema import BackendConfig, VlensConfig, VlensSettings

__all__ = [
    "BackendConfig",
    "VlensConfig",
    "VlensSettings",
    "get_adapter_configs",
    "load_config",
    "resolve_adapter_config",
]
