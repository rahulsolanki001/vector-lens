# Vara — Project Plan

> *Vara* (वार) — Sanskrit for point / space.

---

## 1. Idea & Vision

### The Problem

Vector databases are the backbone of every RAG pipeline, but debugging them is painful and primitive. When retrieval goes wrong — wrong chunks returned, scores unexpectedly low, latency spikes at scale — developers have almost no tooling to understand *why*. The current options are:

- **Print statements and manual score inspection** — tedious, unscalable, and gives no vector-space intuition
- **DB-specific admin UIs** (Qdrant Web UI, Milvus Attu) — locked to one database, no cross-backend comparison, no retrieval diagnostics
- **LLM observability tools** (Arize Phoenix, LangSmith) — trace the full pipeline but treat the vector DB as a black box; no index health, no embedding distribution, no query-level explanation
- **One-off Streamlit scripts** — not reusable, not packaged, not maintained

There is no tool that goes deep on the vector database layer itself — across multiple databases, with a real debugging interface, as a packaged product developers can just install and run.

### The Solution

**Vara is a vector database debugger and visualizer** — a packaged deal of a Python SDK and a local debug UI that works across Qdrant, Pinecone, pgvector, and Milvus without changing your application code.

Think of it as a browser devtools panel, but for your vector database. You install it once, point it at your database, and get:

- **Query debugger** — fire a query, see scores, filter translations, and cross-backend diffs
- **3D vector explorer** — UMAP/t-SNE projection of your embedding space with query highlighting
- **Index health** — opinionated diagnostics on HNSW params, payload indexes, segment count, indexing lag
- **Eval runner** — nDCG, MRR, Recall, latency percentiles, MRL dimension sweep — all in the browser

### Design Principles

**DB-agnostic by design.** Every feature works the same way regardless of which vector database you're running. The same `debug_query()` call, the same health report format, the same UI — whether you're on Qdrant locally or Pinecone in production.

**Zero friction to install.** `pip install vara[qdrant]` and `vara serve`. No Docker required, no account, no API key for Vara itself. Opens in the browser automatically.

**SDK + UI as one package.** The Python library and the React UI ship together. The built UI assets are bundled into the Python wheel — users never run `npm` commands.

**Importable in your pipeline.** Vara is not just a CLI tool. You can call `debug_query()`, `health_check()`, and `diagnose_retrieval()` directly inside your RAG pipeline code for programmatic debugging and CI-integrated eval.

**Async-first, production-safe.** All DB calls are `async`. The library adds zero synchronous blocking to your pipeline. The local server runs independently and never touches your application's event loop.

### Who Is It For

- RAG engineers building and iterating on retrieval pipelines
- Platform teams managing self-hosted vector databases at scale
- Developers switching between vector DB vendors who need a neutral debugging layer
- Anyone who has ever asked "why did my vector search return the wrong chunk"

---

## 2. Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     React UI                            │
│  QueryDebugger │ VectorExplorer │ IndexHealth │ EvalRunner │
└────────────────────────┬────────────────────────────────┘
                         │ REST + WebSocket
┌────────────────────────▼────────────────────────────────┐
│              FastAPI Server  (vara serve)                │
│   /api/query  /api/health  /api/eval  /ws/projection    │
└────────────────────────┬────────────────────────────────┘
                         │ Python calls
┌────────────────────────▼────────────────────────────────┐
│                  Core Debug Engine                       │
│  debug_query()  health_check()  diagnose_retrieval()    │
│  compare_backends()  run_eval()                         │
└────────────────────────┬────────────────────────────────┘
                         │ Adapter interface
┌────────────┬───────────┼───────────┬────────────────────┐
│   Qdrant   │  Pinecone │ pgvector  │      Milvus        │
└────────────┴───────────┴───────────┴────────────────────┘
```

**Key architectural decisions:**
- Adapters are isolated — no adapter imports another, no native SDK types leak upward
- All inter-layer data uses Pydantic models defined in `adapters/base.py`
- `native_query` is populated per-adapter to show exact filter translations in the UI
- UMAP projection runs as an async background job, pushes coordinates over WebSocket
- The React `dist/` is bundled into the Python wheel — `pip install` gives the full UI

---

## 3. Phased Plan

---

### Phase 0 — Project Scaffolding ✅
*Goal: complete skeleton that compiles, imports cleanly, and has the full dev workflow in place before any logic is written.*

- [ ] Repository structure — all directories and stub files
- [ ] `pyproject.toml` — metadata, optional dependency groups (`vara[qdrant]`, `vara[all]`), CLI entry point, ruff + mypy config
- [ ] `.gitignore`, `README.md`, `LICENSE`
- [ ] `vara.yaml.example` — documented config template
- [ ] `Makefile` — `make dev`, `make build`, `make test`, `make lint`, `make check`
- [ ] `docker-compose.dev.yml` — Qdrant, pgvector, Milvus containers for local dev and integration tests
- [ ] GitHub Actions — `ci.yml` (lint + unit tests on every push), `integration.yml` (full suite on main)
- [ ] Python stubs — every module with docstrings, `__all__`, and `NotImplementedError` bodies
- [ ] Frontend scaffold — Vite + React + TypeScript, proxy config, panel stubs, Zustand store stub
- [ ] First unit tests (`test_imports.py`) — verify public API surface, config validation, adapter registry

**Deliverable:** `pip install -e .` works, `python -m pytest -m unit` passes (5/5), full directory tree in place.

---

### Phase 1 — Adapter Layer
*Goal: real DB connections, real queries. The core abstraction that everything else builds on.*

#### Step 1.1 — Base models & ABC (`adapters/base.py`) ✅
All Pydantic models that flow between adapters and the core engine:
- `AdapterConfig`, `QdrantConfig`, `PineconeConfig`, `PgvectorConfig`, `MilvusConfig`
- `CollectionInfo`, `CollectionStats`
- `QueryRequest`, `QueryResult`, `QueryHit`
- `VectorRecord`
- `HealthFinding`, `HealthReport`
- `VecDBAdapter` ABC — `connect`, `disconnect`, `list_collections`, `collection_stats`, `query`, `get_vectors`, `health`

#### Step 1.2 — Qdrant adapter (`adapters/qdrant.py`) ✅
Full implementation using `AsyncQdrantClient`:
- `connect()` — HTTP and gRPC transport, Qdrant Cloud support via `api_key`
- `list_collections()` — handles both single and named vector configs
- `collection_stats()` — HNSW params, payload indexes, segment count, optimizer status
- `query()` — canonical filter → Qdrant `Filter` translation (`$gt`, `$gte`, `$lt`, `$lte`, `$in`, `$and`, `$or`, `$not`), populates `native_query` for UI display
- `get_vectors()` — by ID, handles both UUID and integer IDs
- `health()` — 7 checks: reachability, collection status, ef_construct thresholds, m parameter, segment count, indexing lag %, payload index coverage

#### Step 1.3 — Adapter registry (`adapters/__init__.py`) ✅
`build_adapter(config)` factory with lazy imports — missing optional dependencies only raise at instantiation time, not at `import vara`.

#### Step 1.4 — Pinecone adapter (`adapters/pinecone.py`) ⬜
*Planned — Phase 1 expansion*

#### Step 1.5 — pgvector adapter (`adapters/pgvector.py`) ⬜
*Planned — Phase 1 expansion*

#### Step 1.6 — Milvus adapter (`adapters/milvus.py`) ⬜
*Planned — Phase 1 expansion*

**Deliverable:** `from vara.adapters import build_adapter` + a `vara.yaml` pointing at a real Qdrant instance → working queries and health reports.

---

### Phase 2 — Core Debug Engine
*Goal: the four public SDK functions, fully implemented.*

#### Step 2.1 — `core/rules.py` ⬜
Health check rule codes and severity thresholds as constants — decoupled from adapters so rules are testable in isolation and consistent across backends.

```python
# Example rule codes
HNSW_EF_CONSTRUCT_TOO_LOW = "hnsw_ef_construct_too_low"
MISSING_PAYLOAD_INDEX     = "no_payload_indexes"
HIGH_SEGMENT_COUNT        = "high_segment_count"
INDEXING_LAG              = "indexing_lag"
```

#### Step 2.2 — `core/debug.py` — `debug_query()` and `compare_backends()` ⬜

`debug_query(query_vector, collection, backends, top_k, filters)`:
- Fans out to all specified backends in parallel via `asyncio.gather`
- Returns `DebugQueryResult` — per-backend hits, scores, native queries, timing
- Cross-backend alignment: matches results by document ID, flags documents present in one backend but not another

`compare_backends(query_vector, collection, backend_a, backend_b)`:
- Wrapper around `debug_query` for two-backend diff
- Computes Jaccard similarity of top-k result sets
- Spearman rank correlation of scores
- Returns structured diff for the UI's side-by-side view

#### Step 2.3 — `core/health.py` — `health_check()` ⬜

`health_check(collection, backend)`:
- Calls `adapter.health(collection)` and enriches with cross-cutting logic
- Formats `HealthReport` with Rich for CLI output (`vara check`)
- Returns the same model for both CLI and server/UI use

#### Step 2.4 — `core/diagnose.py` — `diagnose_retrieval()` ⬜

`diagnose_retrieval(query_vector, collection, backend, expected_ids)`:
- Retrieves top-k results (k = max(50, len(expected_ids) * 5))
- For each expected doc: finds its rank, score, score gap vs. top result
- Runs heuristic diagnosis: embedding distance issue vs. filter exclusion vs. index parameter issue
- Returns `DiagnosisResult` with per-doc findings and a plain-English summary

**Deliverable:** All four public SDK functions work end-to-end against a real Qdrant instance. `vara check` prints a health report in the terminal.

---

### Phase 3 — Eval Harness
*Goal: reproducible, UI-driven evaluation with the metrics from the FiQA work.*

#### Step 3.1 — `eval/metrics.py` ⬜
Pure Python implementations (no external eval framework dependency):
- `ndcg_at_k(retrieved_ids, relevant_ids, k)` → float
- `mrr_at_k(retrieved_ids, relevant_ids, k)` → float
- `recall_at_k(retrieved_ids, relevant_ids, k)` → float
- `latency_percentiles(latencies_ms, percentiles)` → dict

#### Step 3.2 — `eval/cache.py` ⬜
Numpy memmap disk cache for corpus embeddings — prevents OOM on large datasets (learned from FiQA). Chunked cosine scoring against the memmap.

#### Step 3.3 — `eval/loaders.py` ⬜
Dataset loaders:
- `FiQALoader` — built-in, pre-validated
- `BEIRLoader` — standard benchmark format (BEIR covers 18 retrieval datasets)
- `CSVLoader` — `query, relevant_ids` columns, flexible delimiter

#### Step 3.4 — `eval/runner.py` — `run_eval()` ⬜

`run_eval(dataset, collection, backend, metrics, dim_truncations, latency_percentiles)`:
- Streams partial results via async generator (for WebSocket live updates)
- Sweeps MRL dimension truncations (1024/512/256/128) in a single pass
- Writes results to JSON (for `vara eval` CLI output)

**Deliverable:** `vara eval --dataset fiqa --backend local-qdrant --collection my_docs` produces a full evaluation report.

---

### Phase 4 — Projection Service
*Goal: interactive 3D vector space — DB-agnostic, incremental, no full rebuild on new docs.*

#### Step 4.1 — `projection/jobs.py` ⬜
Job state machine: `pending → running → complete | error`
- Job ID generation
- Result storage (coordinates + metadata per point)
- Async-safe state updates

#### Step 4.2 — `projection/worker.py` ⬜
- Fetches vectors from adapter via `get_vectors()`
- Runs `umap-learn` with configurable `n_neighbors`, `min_dist`, metric
- **Incremental projection**: new vectors use UMAP `transform()` on the fitted model — no full refit
- t-SNE option for smaller collections
- Pushes coordinate batches over WebSocket as they complete

**Deliverable:** Vector Explorer panel shows a real 3D point cloud from a Qdrant collection, with incremental updates working.

---

### Phase 5 — FastAPI Server
*Goal: the thin HTTP/WebSocket layer that connects the Python core to the React UI.*

#### Step 5.1 — `server/app.py` — FastAPI factory ⬜
- CORS middleware (always allows `localhost:7842` + `localhost:5173` + `vara.yaml cors_origins`)
- Lifespan handler: connect all adapters on startup, disconnect on shutdown
- Static file serving from `vara/server/static/` (the bundled React app)
- Adapter registry injected via FastAPI dependency

#### Step 5.2 — Routes ⬜

```
GET  /api/collections                     → list_collections (all backends)
GET  /api/collections/{name}/health       → health_check()
POST /api/query/debug                     → debug_query()
POST /api/query/diagnose                  → diagnose_retrieval()
POST /api/query/compare                   → compare_backends()
POST /api/eval/run                        → starts eval job, returns job_id
WS   /ws/eval/{job_id}                    → streams eval progress
WS   /ws/projection/{job_id}              → streams UMAP coordinates
GET  /api/config                          → current backend names + connection status
```

#### Step 5.3 — CLI implementation ⬜
`vara serve`:
- Loads `vara.yaml`, connects adapters, starts uvicorn
- Opens browser automatically (unless `--no-browser`)
- Prints connection status table with Rich

`vara check`:
- Loads config, runs `health_check()` on all backends, prints Rich report

`vara dev`:
- Starts Python server with `--reload` and Vite dev server in parallel via `subprocess`

**Deliverable:** `vara serve` starts, browser opens at `localhost:7842`, collections load, health check API responds.

---

### Phase 6 — React UI
*Goal: four panels that actually work, with real data from the Python server.*

#### Step 6.1 — Layout & routing ⬜
- Top navigation: panel tabs
- Left sidebar: backend selector + collection selector (persists across panels, syncs to Zustand store)
- Connection status indicator

#### Step 6.2 — Query Debugger panel ⬜
- Query input (text → embedding, or raw vector paste)
- Filter builder (CodeMirror JSON editor)
- Backend multi-select + top-k slider
- Results: ranked list per backend side-by-side
- Each result card: rank, score, payload preview, expandable native query
- Diff toggle: highlights docs in one backend but not another

#### Step 6.3 — Vector Explorer panel ⬜
- Three.js canvas via `@react-three/fiber`
- UMAP/t-SNE toggle + parameter sliders (`n_neighbors`, `min_dist`)
- Points colored by document source; color-by-score mode when query is active
- Query vector rendered as a distinct shape (not a dot) when a query fires
- Hover tooltip: chunk text preview
- Incremental update: new points appear without full redraw

#### Step 6.4 — Index Health panel ⬜
- Card per backend
- Severity-rated findings list (error / warning / info) with icons
- Expandable detail per finding: raw metric + recommended action
- Re-check button

#### Step 6.5 — Eval Runner panel ⬜
- Dataset upload (CSV or BEIR format)
- Metric checkboxes, dim truncation multi-select
- Live progress bar (WebSocket)
- Charts update in real time: nDCG@10 bar chart, latency percentile chart, MRL dimension curve
- Export results as JSON

**Deliverable:** Full working UI — all four panels functional with real Qdrant data.

---

### Phase 7 — Packaging & Distribution
*Goal: `pip install vara[qdrant]` gives a complete, working tool with no extra steps.*

#### Step 7.1 — Build pipeline ⬜
- `make build-ui` → `npm run build` → copy `ui/dist/` → `vara/server/static/`
- `make build` → build Python wheel with static assets bundled
- Automated in CI: build step runs before PyPI publish

#### Step 7.2 — PyPI publish workflow ⬜
- GitHub Actions `release.yml` — triggers on git tag `v*`
- Builds wheel + sdist, publishes to PyPI via trusted publisher (OIDC, no stored secrets)

#### Step 7.3 — Documentation ⬜
- `docs/` — MkDocs or plain Markdown
- Getting started guide
- vara.yaml reference
- SDK API reference (auto-generated from docstrings)
- "How to debug a bad retrieval" tutorial

---

## 4. Progress Tracker

### ✅ Done

#### Phase 0 — Scaffolding (complete)

| File | Description |
|------|-------------|
| `pyproject.toml` | Package metadata, optional deps, CLI entry point, ruff + mypy config |
| `Makefile` | `dev`, `build`, `build-ui`, `test`, `lint`, `check`, `clean` targets |
| `docker-compose.dev.yml` | Qdrant + pgvector + Milvus local containers |
| `.gitignore` | Python, Node, editor, credential files |
| `vara.yaml.example` | Documented config template with all four backend types |
| `README.md` | Project overview, quick start, adapter table |
| `.github/workflows/ci.yml` | Lint + unit tests on every push, matrix Python 3.10/3.11/3.12 |
| `.github/workflows/integration.yml` | Full suite with Docker on push to main |
| `tests/conftest.py` | Shared fixtures — sample vectors, DB URLs |
| `tests/unit/test_imports.py` | 5 unit tests — all passing |
| `tests/fixtures/pg_init.sql` | pgvector test table init |
| `ui/package.json` | React + Three.js + Recharts + Zustand dependencies |
| `ui/tsconfig.json` | TypeScript strict config |
| `ui/vite.config.ts` | Vite + React plugin + `/api` + `/ws` proxy |
| `ui/index.html` | Entry HTML |
| `ui/src/main.tsx` | React root |
| `ui/src/App.tsx` | Root component stub |
| `ui/src/panels/*.tsx` | QueryDebugger, VectorExplorer, IndexHealth, EvalRunner stubs |
| `ui/src/api/client.ts` | REST + WebSocket client type stubs |
| `ui/src/store/index.ts` | Zustand store stub |
| All `vara/**/__init__.py` | Module stubs with docstrings and `__all__` |
| All `vara/core/*.py` | `debug`, `diagnose`, `health`, `rules` stubs |
| All `vara/eval/*.py` | `runner`, `metrics`, `loaders`, `cache` stubs |
| All `vara/projection/*.py` | `worker`, `jobs` stubs |
| All `vara/server/**/*.py` | `app`, routes, websocket stubs |
| All `vara/adapters/*.py` | `qdrant`, `pinecone`, `pgvector`, `milvus` stubs |

#### Phase 1 — Adapter Layer (Qdrant complete)

| File | Description |
|------|-------------|
| `vara/adapters/base.py` | Full Pydantic model set + `VecDBAdapter` ABC |
| `vara/adapters/__init__.py` | `build_adapter()` factory with lazy imports |
| `vara/adapters/qdrant.py` | Full Qdrant adapter — connect, query, health (7 checks), filter translation |
| `vara/config/schema.py` | `VaraSettings`, `BackendConfig`, `VaraConfig` with full validation |
| `vara/config/loader.py` | `load_config()`, `resolve_adapter_config()`, `get_adapter_configs()` |
| `vara/config/__init__.py` | Clean public exports |
| `vara/cli.py` | CLI skeleton — `serve`, `check`, `eval`, `dev` commands |
| `vara/__init__.py` | Public SDK surface — `debug_query`, `health_check`, `diagnose_retrieval`, `compare_backends` |

---

### ⬜ In Progress / Up Next

| Phase | Next Step |
|-------|-----------|
| Phase 2 | `core/rules.py` → `core/debug.py` → `core/health.py` → `core/diagnose.py` |
| Phase 3 | `eval/metrics.py` → `eval/cache.py` → `eval/loaders.py` → `eval/runner.py` |
| Phase 4 | `projection/jobs.py` → `projection/worker.py` |
| Phase 5 | `server/app.py` → routes → CLI `serve` + `check` implementation |
| Phase 6 | Layout + Query Debugger → Vector Explorer → Index Health → Eval Runner |
| Phase 7 | Build pipeline → PyPI workflow → docs |

---

### 🧪 Test Coverage

| Suite | Tests | Status |
|-------|-------|--------|
| `tests/unit/test_imports.py` | 5 | ✅ All passing |
| `tests/unit/test_config.py` | — | ⬜ To write in Phase 2 |
| `tests/unit/test_adapters.py` | — | ⬜ To write in Phase 1 |
| `tests/integration/test_qdrant.py` | — | ⬜ To write in Phase 1 |
| `tests/integration/test_eval.py` | — | ⬜ To write in Phase 3 |

---

## 5. Stack Summary

| Layer | Technology | Why |
|-------|-----------|-----|
| Python version | 3.10+ | `match` statements, native `X \| Y` unions |
| Package manager | pip + pyproject.toml (hatchling) | Standard, no extra tooling |
| Web framework | FastAPI + uvicorn | Async-native, WebSocket support, auto OpenAPI docs |
| CLI | Typer | Clean `--help`, subcommands, Rich integration |
| Validation | Pydantic v2 | Fast, strict, great error messages |
| DB clients | qdrant-client (async), pinecone, asyncpg+pgvector, pymilvus | Official SDKs, lazy-imported |
| Projection | umap-learn + scikit-learn | Best-in-class UMAP, `transform()` for incremental |
| Eval math | numpy + scipy | ndcg/MRR from scratch, memmap for OOM prevention |
| Lint + format | ruff | Replaces flake8 + black + isort, dramatically faster |
| Type checking | mypy (strict on core) | Catches bugs before runtime |
| Testing | pytest + pytest-asyncio | Async test support, marker-based unit/integration split |
| Frontend | React 18 + TypeScript | Type-safe, component model |
| Build tool | Vite | Fast HMR, simple proxy config |
| 3D rendering | Three.js via @react-three/fiber | React-friendly Three.js wrapper |
| Charts | Recharts | Composable, TypeScript-native |
| State | Zustand | Lightweight, no boilerplate |
| CI | GitHub Actions | Free for open source, Docker support |
