# Vara

Vara is a vector database debugger and visualizer for RAG developers. It is
designed as a local Python SDK plus debug UI that can inspect query behavior,
index health, vector-space structure, and retrieval eval results across vector
database backends.

The project is currently in early scaffold and backend-foundation work. Qdrant
is the first implemented adapter.

## Current Capabilities

- Config loading and validation from `vara.yaml`
- Async adapter abstraction for vector databases
- Qdrant adapter with query, collection stats, vector fetch, and health checks
- Core query debugging helpers:
  - `debug_query`
  - `compare_backends`
  - `health_check`
  - `diagnose_retrieval`

## Planned Panels

- Query Debugger
- Vector Explorer
- Index Health
- Eval Runner

## Quick Start

```bash
pip install -e ".[qdrant,dev]"
cp vara.yaml.example vara.yaml
docker compose -f docker-compose.dev.yml up -d qdrant
```

CLI/server commands are scaffolded but not implemented yet.

## Adapter Status

| Backend | Status |
|---------|--------|
| Qdrant | First implementation complete |
| Pinecone | Planned |
| pgvector | Planned |
| Milvus | Planned |

## Development

```bash
make install-dev
make test-unit
make check
```

The React UI scaffold lives in `ui/`. Built UI assets will eventually be copied
into `vara/server/static/` and bundled into the Python wheel.
