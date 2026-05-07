"""
vlens.config.loader — Load and resolve vlens.yaml.

Handles:
  - Reading vlens.yaml from disk
  - Interpolating ${ENV_VAR} references
  - Validating config structure via Pydantic
  - Type-dispatching BackendConfig → typed adapter configs
  - Convenience helper to build all adapter configs in one call

Currently supported backend types: qdrant
Planned (Phase 1 expansion): pinecone, pgvector, milvus
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import yaml

from vlens.adapters.base import (
    AdapterConfig,
    MilvusConfig,
    PgvectorConfig,
    PineconeConfig,
    QdrantConfig,
)
from vlens.config.schema import BackendConfig, VlensConfig

# Matches ${VAR_NAME} anywhere inside a string value
_ENV_VAR_RE = re.compile(r"\$\{([^}]+)\}")

# Backend types fully implemented in this release
_SUPPORTED_TYPES = {"milvus", "pgvector", "pinecone", "qdrant"}

# Backend types recognised but not yet implemented
_PLANNED_TYPES = {"weaviate","chromadb"}


# ── Environment variable interpolation ───────────────────────────────────────


def _interpolate(value: str) -> str:
    """
    Replace every ${VAR} in a string with its environment variable value.

    Raises ValueError if any referenced variable is not set, so users
    get a clear error at startup rather than a silent empty string.
    """

    def _replace(match: re.Match[str]) -> str:
        var_name = match.group(1)
        resolved = os.environ.get(var_name)
        if resolved is None:
            raise ValueError(
                f"Environment variable '{var_name}' referenced in vlens.yaml is not set.\n"
                f"Set it in your shell or .env file before running `vlens serve`."
            )
        return resolved

    return _ENV_VAR_RE.sub(_replace, value)


def _interpolate_dict(data: dict[str, Any]) -> dict[str, Any]:
    """
    Recursively walk a parsed YAML dict and interpolate all string values.

    Handles nested dicts and lists of any depth.
    Non-string scalar values (int, bool, float, None) are passed through unchanged.
    """
    result: dict[str, Any] = {}
    for k, v in data.items():
        if isinstance(v, str):
            result[k] = _interpolate(v)
        elif isinstance(v, dict):
            result[k] = _interpolate_dict(v)
        elif isinstance(v, list):
            result[k] = [
                _interpolate_dict(item)
                if isinstance(item, dict)
                else (_interpolate(item) if isinstance(item, str) else item)
                for item in v
            ]
        else:
            result[k] = v
    return result


# ── Config loading ────────────────────────────────────────────────────────────


def load_config(path: str | Path = "vlens.yaml") -> VlensConfig:
    """
    Load, interpolate, and validate vlens.yaml.

    Steps:
      1. Read the YAML file from disk
      2. Recursively resolve ${ENV_VAR} references
      3. Validate the resulting dict against VlensConfig (Pydantic)

    Args:
        path: Path to vlens.yaml. Defaults to vlens.yaml in the current directory.

    Raises:
        FileNotFoundError: Config file does not exist.
        ValueError:        An ${ENV_VAR} reference is unset.
        ValidationError:   YAML structure is invalid (Pydantic will explain what's wrong).
    """
    config_path = Path(path)

    if not config_path.exists():
        raise FileNotFoundError(
            f"Config file not found: {config_path.resolve()}\n"
            f"  → Copy the example and fill in your backends:\n"
            f"    cp vlens.yaml.example vlens.yaml"
        )

    with config_path.open() as f:
        raw = yaml.safe_load(f) or {}

    if not isinstance(raw, dict):
        raise ValueError(
            f"vlens.yaml must be a YAML mapping at the top level, got: {type(raw).__name__}"
        )

    interpolated = _interpolate_dict(raw)
    return VlensConfig.model_validate(interpolated)


# ── Adapter config resolution ─────────────────────────────────────────────────


def resolve_adapter_config(backend: BackendConfig) -> AdapterConfig:
    """
    Type-dispatch a raw BackendConfig into a fully-typed adapter config.

    The raw BackendConfig uses `extra = "allow"` to capture all fields
    from vlens.yaml. This function converts it to the strongly-typed
    config model for the specific adapter (e.g. QdrantConfig).

    Args:
        backend: A BackendConfig parsed from vlens.yaml.

    Returns:
        A typed AdapterConfig subclass (QdrantConfig, etc.)

    Raises:
        ValueError: Backend type is unknown or not yet implemented.
    """
    # model_dump() preserves all extra fields set by `extra = "allow"`
    data = backend.model_dump()

    match backend.type:
        case "qdrant":
            return QdrantConfig(**data)

        case "pgvector":
            return PgvectorConfig(**data)
        
        case "milvus":
            return MilvusConfig(**data)
        
        case "pinecone":
            return PineconeConfig(**data)


        case t if t in _PLANNED_TYPES:
            raise ValueError(
                f"Backend type '{t}' ('{backend.name}') is planned but not yet "
                f"implemented in this version of Vector Lens.\n"
                f"Currently supported: {sorted(_SUPPORTED_TYPES)}\n"
                f"Track progress at: https://github.com/yourusername/vector-lens"
            )

        case _:
            raise ValueError(
                f"Unknown backend type '{backend.type}' for backend '{backend.name}'.\n"
                f"Supported: {sorted(_SUPPORTED_TYPES)}\n"
                f"Planned:   {sorted(_PLANNED_TYPES)}"
            )


def get_adapter_configs(config: VlensConfig) -> list[AdapterConfig]:
    """
    Resolve all backends in a VlensConfig into typed adapter configs.

    Convenience wrapper around resolve_adapter_config() that processes
    the full backends list and gives a clear aggregated error if any
    backend fails to resolve.

    Args:
        config: A loaded VlensConfig (from load_config()).

    Returns:
        List of typed AdapterConfig instances, one per backend entry.

    Raises:
        ValueError: One or more backends have invalid or unsupported config.
    """
    if not config.backends:
        raise ValueError(
            "No backends configured in vlens.yaml.\n"
            "Add at least one backend under the 'backends:' key.\n"
            "See vlens.yaml.example for reference."
        )

    resolved: list[AdapterConfig] = []
    errors: list[str] = []

    for backend in config.backends:
        try:
            resolved.append(resolve_adapter_config(backend))
        except ValueError as exc:
            errors.append(f"  [{backend.name}]: {exc}")

    if errors:
        raise ValueError("Failed to resolve one or more backend configs:\n" + "\n".join(errors))

    return resolved
