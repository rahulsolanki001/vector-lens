# Vara Progress Tracker

Last updated: 2026-05-01 (night)

## Current Status

Vara's Python backend is functionally complete. Phases 0–5 are done: scaffolding,
Qdrant adapter, config loading, core debug engine, eval harness, projection
service, and the full FastAPI server with REST routes, WebSocket streaming, and
CLI commands. The remaining work is the React UI (Phase 6) and packaging
(Phase 7).

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

### Phase 4 - Projection Service, Complete

| File | Status |
|------|--------|
| `vara/projection/jobs.py` | `ProjectionParams`, extended `ProjectionJob` (progress, timestamps), async-safe `ProjectionJobStore` with state transitions and fitted-model cache |
| `vara/projection/worker.py` | `run_projection` async generator — fetches vectors, runs UMAP/t-SNE in thread-pool executor, streams `ProjectionPoint` batches, updates job store; incremental UMAP via `transform()` using `base_job_id` |

### Phase 5 - FastAPI Server, Complete

| File | Status |
|------|--------|
| `vara/server/deps.py` | Shared FastAPI dependency helpers: `get_adapters`, `get_job_store`, `get_eval_jobs`, `get_vara_config`, `require_adapter` |
| `vara/server/app.py` | Lifespan connects all adapters + initialises stores; CORS with extra origins from config; REST routers + WebSocket routes registered; React SPA served from `static/` when present |
| `vara/server/routes/config.py` | `GET /api/config` — backend names and types |
| `vara/server/routes/collections.py` | `GET /api/collections` (fan-out, fault-tolerant) + `GET /api/collections/{backend}/{collection}/health` |
| `vara/server/routes/query.py` | `POST /api/query/debug`, `compare`, `diagnose` — typed request models, calls core engine |
| `vara/server/routes/eval.py` | `POST /api/eval/run` — loads CSV dataset, starts background task, returns `job_id` immediately |
| `vara/server/websocket/eval_stream.py` | `WS /ws/eval/{job_id}` — drains asyncio Queue, forwards `EvalProgress` as JSON until sentinel or error |
| `vara/server/websocket/projection_stream.py` | `WS /ws/projection` — accepts params in first JSON message, creates job, streams `ProjectionPoint` batches, supports incremental `base_job_id` |
| `vara/cli.py` | `vara serve` (uvicorn + auto browser-open), `vara check` (Rich health table), `vara eval` (CLI eval → JSON file), `vara dev` (uvicorn --reload + Vite subprocess) |

## Verification

- No empty Python modules remain under `vara/`.
- Python syntax compilation passed for the `vara/` package with Python 3.11.
- Project dependencies installed successfully with `pip install -e ".[all,dev]"`.
- Unit test suite passed: `pytest -m unit -v` -> 24 passed (pre Phase 3 additions).
- Ruff passed: `ruff check vara/ tests/`.
- Mypy passed: `mypy vara/`.
- Mypy currently prints a harmless note about unused overrides for optional third-party module sections.
- All Phase 5 server and CLI imports verified clean against project venv.

## Next Steps

### 1. React UI (Phase 6)

Recommended order:

1. Layout, routing, and backend/collection selector sidebar
2. Query Debugger panel — vector input, filter builder, per-backend results, diff view
3. Index Health panel — findings cards with severity, re-check button
4. Eval Runner panel — dataset upload, live progress chart, export
5. Vector Explorer panel — Three.js 3D point cloud, UMAP/t-SNE toggle, incremental updates

### 2. Packaging (Phase 7)

- Build pipeline: `make build-ui` → copy dist → `make build` (wheel with bundled UI)
- PyPI publish GitHub Action on `v*` tags
- Documentation
