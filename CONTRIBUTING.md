# Contributing to Vector Lens

Thank you for your interest in contributing! This document covers how to set up your dev environment, the project structure, and the process for submitting changes.

---

## Table of Contents

- [Getting Started](#getting-started)
- [Project Structure](#project-structure)
- [Development Workflow](#development-workflow)
- [Code Quality](#code-quality)
- [Testing](#testing)
- [Submitting a Pull Request](#submitting-a-pull-request)
- [Adding a New Adapter](#adding-a-new-adapter)

---

## Getting Started

**Prerequisites:** Python 3.10+, Node.js 18+, Git.

```bash
git clone https://github.com/rahulsolanki001/vector-lens.git
cd vector-lens

# Install Python package with all extras and dev deps
pip install -e ".[all,dev]"

# Install UI deps
cd ui && npm install && cd ..

# Start backend + UI with hot-reload
vlens dev
```

Then open [http://localhost:5173](http://localhost:5173).

For a local vector DB to test against, spin up the dev stack:

```bash
docker compose -f docker-compose.dev.yml up -d
```

Copy and edit the example config:

```bash
cp vlens.yaml.example vlens.yaml
# Edit vlens.yaml to point at your backends
```

---

## Project Structure

```
vlens/                   Python package
  adapters/              DB adapter implementations (qdrant, pgvector, milvus, pinecone)
  core/                  Debug engine (debug_query, health_check, diagnose_retrieval, compare_backends)
  config/                YAML config loading and Pydantic models
  eval/                  Eval harness (metrics, loaders, runner, cache)
  projection/            UMAP/t-SNE background jobs
  server/                FastAPI app, routes, WebSocket handlers
  cli.py                 Typer CLI (vlens serve / check / eval / dev)

ui/                      React frontend (Vite + TypeScript + Tailwind)
  src/
    api/                 API client + TypeScript types
    components/          Shared UI components
    panels/              Full-page panels (QueryDebugger, IndexHealth, EvalRunner, VectorExplorer)
    store/               Zustand global state

tests/
  unit/                  Fast tests, no external dependencies
  integration/           Tests against live DB containers
```

---

## Development Workflow

- Backend changes: the `vlens dev` command starts uvicorn with `--reload`, so Python changes apply immediately.
- UI changes: Vite HMR updates the browser on save.
- Run only the backend: `uvicorn vlens.server.app:app --reload --port 7842`
- Run only the UI: `cd ui && npm run dev`

---

## Code Quality

All checks must pass before a PR can be merged.

```bash
make check          # ruff lint + mypy type check
make typecheck-ui   # TypeScript type check
```

Auto-fix formatting:

```bash
make fmt
```

### Style notes

- Python: ruff enforces formatting and import order. Line length is 100.
- TypeScript: no linter enforced, but keep consistent with the surrounding code.
- No comments explaining *what* code does — only *why* when it's non-obvious.
- No docstrings on obvious helpers; keep module-level docstrings short.

---

## Testing

```bash
make test-unit              # fast, no external deps (pytest -m unit)
make test-integration       # requires Docker (spins up Qdrant, pgvector, Milvus)
```

Unit tests live in `tests/unit/`. Every new module should have corresponding unit coverage. Integration tests live in `tests/integration/` and are run in CI on merges to `main`.

When adding tests:
- Mark fast tests with `@pytest.mark.unit`
- Mark DB-dependent tests with `@pytest.mark.integration`
- Use `pytest-asyncio` for async test functions (mode is `auto`)

---

## Submitting a Pull Request

1. Fork the repo and create a branch from `main`: `git checkout -b feat/your-feature`
2. Make your changes and add tests.
3. Run `make check` and `make test-unit` — both must pass.
4. Open a PR against `main` with a clear description of what changed and why.
5. Link any relevant issues.

PR titles should follow the format: `type: short description` where type is one of `feat`, `fix`, `refactor`, `docs`, `test`, or `chore`.

---

## Adding a New Adapter

All adapters implement the `VecDBAdapter` ABC defined in `vlens/adapters/base.py`. The required methods are:

| Method | Description |
|--------|-------------|
| `connect()` | Establish connection / connection pool |
| `disconnect()` | Tear down connection |
| `list_collections()` | Return `list[CollectionInfo]` |
| `collection_stats(collection)` | Return `CollectionStats` |
| `query(request)` | Execute a vector query, return `QueryResult` |
| `get_vectors(collection, ids)` | Fetch vectors by ID, return `list[VectorRecord]` |
| `health(collection)` | Run health checks, return `HealthReport` |

Steps to add a new adapter:

1. Create `vlens/adapters/yourdb.py` implementing `VecDBAdapter`.
2. Add a config model (`YourDbConfig`) in `vlens/adapters/base.py` following the existing pattern.
3. Register it in `vlens/adapters/__init__.py` `build_adapter()` factory.
4. Add an optional dependency group in `pyproject.toml` and update the `all` group.
5. Add an entry to the `vlens.yaml.example` config file.
6. Add health check logic that covers at minimum: reachability, collection existence, and index presence.
7. Add unit tests in `tests/unit/` and update `README.md`'s adapter table.

Use the `vlens/adapters/qdrant.py` or `vlens/adapters/pgvector.py` implementations as reference.

---

## Questions?

Open an issue on [GitHub](https://github.com/rahulsolanki001/vector-lens/issues).
