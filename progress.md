# Vara Progress Tracker

Last updated: 2026-05-01

## Current Status

Vara is in the scaffold-first stage with the backend foundation underway. The
repository now has an import-clean Python skeleton, Phase 0 project files, the
Qdrant adapter, config loading, and the first pass of the core debug engine.
Python dependencies are installed locally and the baseline unit/lint/type checks
are green. Phase 3 is complete: retrieval metrics, CSV dataset loading, the
disk-backed embedding cache, and the async eval runner are all implemented.

## Done

### Phase 0 - Scaffolding

| File or Directory | Status |
|-------------------|--------|
| `pyproject.toml` | Package metadata, optional dependencies, CLI entry point, ruff/mypy/pytest config |
| `Makefile` | Developer command targets defined |
| `LICENSE` | Present |
| `.gitignore` | Python, Node, editor, credential, and generated asset ignores |
| `README.md` | Basic project overview, quick start, and adapter status |
| `vara.yaml.example` | Documented starter config with Qdrant active and planned adapters commented |
| `docker-compose.dev.yml` | Local Qdrant, pgvector/Postgres, and Milvus stack |
| `.github/workflows/ci.yml` | Python and UI checks workflow |
| `.github/workflows/integration.yml` | Live DB integration workflow |
| `tests/` | Initial pytest fixtures, import smoke tests, pgvector init fixture |
| `ui/` | Minimal Vite + React + TypeScript scaffold and panel placeholders |
| `vara/server/static/.gitkeep` | Placeholder for bundled UI assets |
| Python package skeleton | Empty modules replaced with import-clean stubs/placeholders |

Notes:

- Root-level `ci.yml` and `integration.yml` are still present as earlier drafts.
- CLI commands are still skeleton commands and intentionally raise `NotImplementedError`.

### Phase 1 - Adapter Layer, Qdrant Complete

| File | Status |
|------|--------|
| `vara/adapters/base.py` | Full shared Pydantic model set and `VecDBAdapter` ABC |
| `vara/adapters/__init__.py` | `build_adapter()` factory with lazy imports |
| `vara/adapters/qdrant.py` | Async Qdrant adapter with connect, query, stats, vector fetch, filter translation, and health checks |
| `vara/adapters/pinecone.py` | Import-clean planned adapter placeholder |
| `vara/adapters/pgvector.py` | Import-clean planned adapter placeholder |
| `vara/adapters/milvus.py` | Import-clean planned adapter placeholder |

### Config Layer

| File | Status |
|------|--------|
| `vara/config/schema.py` | `VaraSettings`, `BackendConfig`, `VaraConfig`, validation helpers |
| `vara/config/loader.py` | YAML loading, env interpolation, adapter config resolution |
| `vara/config/__init__.py` | Public config exports |

### Phase 2 - Core Debug Engine, First Pass Complete

| File | Status |
|------|--------|
| `vara/core/__init__.py` | Exports core SDK functions |
| `vara/core/rules.py` | Shared severity/status constants, rule codes, thresholds, finding helpers |
| `vara/core/debug.py` | Multi-backend `debug_query()`, two-backend `compare_backends()`, hit alignment, Jaccard and Spearman metrics |
| `vara/core/health.py` | `health_check()` and concurrent `health_check_many()` wrapper |
| `vara/core/diagnose.py` | `diagnose_retrieval()` with heuristic per-document findings |

### Import-Clean Placeholders

| Area | Status |
|------|--------|
| `vara/eval/` | Placeholder metric, loader, cache, and runner APIs |
| `vara/projection/` | Placeholder job state and worker APIs |
| `vara/server/` | Minimal FastAPI app factory and 501 route placeholders |
| `vara/server/websocket/` | Placeholder WebSocket stream handlers |

### Phase 3 - Eval Harness, Complete

| File | Status |
|------|--------|
| `vara/eval/metrics.py` | Implemented binary nDCG@k, MRR@k, recall@k, and latency percentiles |
| `tests/unit/test_eval_metrics.py` | Unit coverage for ranking metrics, duplicate handling, invalid k, and percentile edge cases |
| `vara/eval/loaders.py` | Implemented `EvalQuery`, `EvalDataset`, and strict `CSVLoader` requiring query text, vector, and relevant IDs |
| `tests/unit/test_eval_loaders.py` | Unit coverage for CSV aliases, JSON/delimited values, and validation errors |
| `vara/eval/cache.py` | Implemented numpy memmap-backed `EmbeddingCache` with open/close/get/set and context manager |
| `vara/eval/runner.py` | Implemented async `run_eval` generator streaming `EvalProgress` with running-mean metrics, latency percentiles, and optional dim truncations |
| `tests/unit/test_eval_cache.py` | Unit coverage for round-trip, persistence across reopen, overflow, dimension mismatch, and context manager |
| `tests/unit/test_eval_runner.py` | Unit coverage via fake adapter: event count, metric accumulation, dim truncations, latency tracking, unknown metric error |

## Verification

- No empty Python modules remain under `vara/`.
- Python syntax compilation passed for the `vara/` package with Python 3.11.
- Project dependencies installed successfully with `pip install -e ".[all,dev]"`.
- Unit test suite passed: `pytest -m unit -v` -> 24 passed.
- Ruff passed: `ruff check vara/ tests/`.
- Mypy passed: `mypy vara/`.
- Mypy currently prints a harmless note about unused overrides for optional third-party module sections.

## Next Steps

### 1. Projection Layer

Recommended order:

1. `vara/projection/jobs.py` — job state model and persistence
2. `vara/projection/worker.py` — async projection worker

### 2. Server Layer

- Implement real `server/app.py` lifespan/config loading.
- Replace 501 route placeholders with calls into config, adapters, and core.
