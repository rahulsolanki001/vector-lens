"""
vara.config.schema — Pydantic models for vara.yaml.

Defines the exact shape of the configuration file.
Environment variable interpolation (${VAR}) is handled upstream in loader.py
before these models ever see the data — so all fields here receive plain values.

Schema overview:

    vara:                        # VaraSettings
      port: 7842
      open_browser: true
      log_level: info
      cors_origins: []           # extra origins to allow (for remote UI access)

    backends:                    # list[BackendConfig]
      - name: local-qdrant
        type: qdrant
        host: localhost
        port: 6333

Validation rules:
  - Backend names must be unique across the list
  - Backend names must be slug-like (alphanumeric, hyphens, underscores)
  - Port must be in the valid range 1-65535
  - log_level must be one of: debug, info, warning, error
  - At most 20 backends (sanity limit — not a hard product constraint)
"""

from __future__ import annotations

import re

from pydantic import BaseModel, Field, field_validator, model_validator

# Backend name must be a safe identifier — used in URLs and log lines
_NAME_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}$")

_VALID_LOG_LEVELS = {"debug", "info", "warning", "error"}
_VALID_BACKEND_TYPES = {"qdrant", "pinecone", "pgvector", "milvus"}

# Planned but not yet implemented — used to give helpful error messages
_PLANNED_BACKEND_TYPES: set[str] = set()

_MAX_BACKENDS = 20


# ── VaraSettings ──────────────────────────────────────────────────────────────


class VaraSettings(BaseModel):
    """
    Top-level [vara] section of vara.yaml.

    Controls the local server behaviour. All fields have sensible defaults
    so the entire section can be omitted from vara.yaml.
    """

    model_config = {"extra": "forbid"}  # typos in vara.yaml become errors, not silent ignores

    port: int = Field(
        default=7842,
        description="Port for the Vara local server.",
    )
    open_browser: bool = Field(
        default=True,
        description="Automatically open the browser when `vara serve` starts.",
    )
    log_level: str = Field(
        default="info",
        description="Server log verbosity. One of: debug, info, warning, error.",
    )
    cors_origins: list[str] = Field(
        default_factory=list,
        description=(
            "Extra allowed CORS origins for the API server. "
            "Useful when running the UI on a different host during development. "
            "localhost:7842 and localhost:5173 are always allowed."
        ),
    )

    @field_validator("port")
    @classmethod
    def validate_port(cls, v: int) -> int:
        if not (1 <= v <= 65535):
            raise ValueError(f"port must be between 1 and 65535, got {v}.")
        if v < 1024:
            # Not an error, but worth a warning — Pydantic validators can't emit
            # warnings directly, so we surface this via the description/docs.
            pass
        return v

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        normalised = v.lower().strip()
        if normalised not in _VALID_LOG_LEVELS:
            raise ValueError(
                f"log_level '{v}' is invalid. "
                f"Must be one of: {', '.join(sorted(_VALID_LOG_LEVELS))}."
            )
        return normalised

    @field_validator("cors_origins")
    @classmethod
    def validate_cors_origins(cls, v: list[str]) -> list[str]:
        for origin in v:
            if not origin.startswith(("http://", "https://")):
                raise ValueError(f"CORS origin '{origin}' must start with http:// or https://.")
        return v


# ── BackendConfig ─────────────────────────────────────────────────────────────


class BackendConfig(BaseModel):
    """
    A single entry under the [backends] list in vara.yaml.

    `extra = "allow"` is intentional — adapter-specific fields (host, port,
    api_key, dsn, etc.) are captured here as raw extras and unpacked into the
    strongly-typed adapter config (QdrantConfig, etc.) in loader.py.

    Only `name` and `type` are validated at this level.
    Adapter-specific field validation happens in the typed config models
    in vara.adapters.base.
    """

    model_config = {"extra": "allow"}

    name: str = Field(
        description=(
            "Unique name for this backend. Used in API calls, log lines, and the UI. "
            "Must be alphanumeric with hyphens/underscores (e.g. 'local-qdrant', 'prod_qdrant')."
        ),
    )
    type: str = Field(
        description=(f"Backend type. Supported: {sorted(_VALID_BACKEND_TYPES)}."),
    )

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Backend name cannot be empty.")
        if not _NAME_RE.match(v):
            raise ValueError(
                f"Backend name '{v}' is invalid. "
                f"Use only letters, numbers, hyphens, and underscores "
                f"(1-64 characters, must start with a letter or number)."
            )
        return v

    @field_validator("type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        normalised = v.lower().strip()
        if normalised not in _VALID_BACKEND_TYPES:
            known = sorted(_VALID_BACKEND_TYPES)
            raise ValueError(f"Backend type '{v}' is not recognised. Valid types: {known}.")
        return normalised


# ── VaraConfig ────────────────────────────────────────────────────────────────


class VaraConfig(BaseModel):
    """
    Root config model — the full contents of vara.yaml.

    Fields:
        vara:     Server settings (optional, all defaults are sensible).
        backends: List of DB backend connections (at least one required to use
                  `vara serve`, but optional for programmatic SDK use).
    """

    model_config = {"extra": "forbid"}

    vara: VaraSettings = Field(
        default_factory=VaraSettings,
        description="Global Vara server settings.",
    )
    backends: list[BackendConfig] = Field(
        default_factory=list,
        description="List of vector DB backends to connect to.",
    )

    @field_validator("backends")
    @classmethod
    def validate_backends(cls, backends: list[BackendConfig]) -> list[BackendConfig]:
        # Sanity limit
        if len(backends) > _MAX_BACKENDS:
            raise ValueError(
                f"Too many backends configured ({len(backends)}). Maximum is {_MAX_BACKENDS}."
            )

        # Unique names
        names = [b.name for b in backends]
        seen: set[str] = set()
        duplicates: set[str] = set()
        for n in names:
            if n in seen:
                duplicates.add(n)
            seen.add(n)

        if duplicates:
            raise ValueError(
                f"Backend names must be unique. Duplicate name(s) found: {sorted(duplicates)}."
            )

        return backends

    @model_validator(mode="after")
    def validate_no_empty_backends(self) -> VaraConfig:
        """
        Post-validation check: all configured backend types are supported.
        _PLANNED_BACKEND_TYPES is now empty — all four types are implemented.
        """
        if not self.backends:
            return self  # loader.py handles the empty-backends case at runtime

        unsupported = [b for b in self.backends if b.type in _PLANNED_BACKEND_TYPES]
        if unsupported and len(unsupported) == len(self.backends):
            names = [f"'{b.name}' ({b.type})" for b in unsupported]
            raise ValueError(
                f"None of your configured backends are supported in this version of Vara.\n"
                f"Unsupported types: {', '.join(names)}.\n"
                f"Supported types: qdrant, pinecone, pgvector, milvus."
            )

        return self

    def get_backend(self, name: str) -> BackendConfig:
        """
        Look up a backend by name.

        Args:
            name: The backend name as defined in vara.yaml.

        Returns:
            The matching BackendConfig.

        Raises:
            KeyError: No backend with that name exists.
        """
        for backend in self.backends:
            if backend.name == name:
                return backend
        available = [b.name for b in self.backends]
        raise KeyError(f"No backend named '{name}' in config. Available backends: {available}.")

    @property
    def backend_names(self) -> list[str]:
        """Ordered list of all configured backend names."""
        return [b.name for b in self.backends]

    @property
    def qdrant_backends(self) -> list[BackendConfig]:
        """All backends of type 'qdrant'."""
        return [b for b in self.backends if b.type == "qdrant"]
