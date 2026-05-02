# Vara

Vara is a vector database debugger and visualizer for RAG developers. It provides
a local Python SDK and a dark-themed React UI for inspecting query behaviour,
index health, vector-space structure, and retrieval eval results across multiple
vector database backends simultaneously.

## Features

### Query Debugger
- Run a vector query against one or more backends and inspect results side by side
- **Debug mode** — per-backend hit lists with latency, score bars, and payload
- **Compare mode** — Jaccard similarity, rank Spearman ρ, score Spearman ρ, and
  diff-highlighted hit lists between two backends
- **Diagnose mode** — per-expected-ID findings (not found, found but not retrieved,
  score gap to top) with actionable recommendations

### Index Health
- Per-backend health status (healthy / degraded / unhealthy) with a single click
- Actionable findings: missing HNSW index, empty collection, reachability errors
- Collapsible stats: vector count, dimension, distance metric, index type, disk usage

### Eval Runner
- Run a retrieval eval from a CSV dataset over any configured backend
- Live WebSocket streaming of nDCG@k, MRR@k, Recall@k, and p50/p95/p99 latency
- Recharts line chart streaming metrics per query
- Export final results as JSON

### Vector Explorer
- UMAP or t-SNE projection of any subset of vectors from the index
- **2D and 3D** output — switch between modes with the dimension toggle
- Bloom/glow post-processing (via `@react-three/postprocessing`)
- Points colored by any payload field with an auto-generated palette
- **HDBSCAN clustering** — one click runs density clustering on the projected
  coordinates; noise points rendered in muted gray; color-mode toggle between
  field coloring and cluster coloring
- Click to select a point and inspect full payload in a slide-in side panel
- Hover shows a tooltip (id + payload fields) and K nearest-neighbour lines in
  projected space
- Auto-rotate when idle; orbit controls lock to pan/zoom only in 2D mode
- HUD overlay: point count, algorithm, dimension mode, elapsed time
- Incremental projection via "Add More IDs" (reuses fitted UMAP model)

## Quick Start

```bash
pip install -e ".[qdrant,pgvector,dev]"
cp vara.yaml.example vara.yaml

# Start a local Qdrant and/or pgvector instance
docker compose -f docker-compose.dev.yml up -d

# Start the backend + Vite dev server together
vara dev
```

Then open [http://localhost:5173](http://localhost:5173).

## Configuration

```yaml
# vara.yaml
vara:
  host: 0.0.0.0
  port: 7842

backends:
  - name: local-qdrant
    type: qdrant
    url: http://localhost:6333

  - name: local-pgvector
    type: pgvector
    dsn: postgresql://vara:vara@localhost:5432/vara
```

## CLI

```bash
vara serve          # start the API server (opens browser)
vara dev            # server + Vite hot-reload (development)
vara check          # print a health table for all configured backends
vara eval           # run a retrieval eval from a CSV and write JSON results
```

## Adapter Status

| Backend | Status |
|---------|--------|
| Qdrant | Complete — query, health, stats, filters, vector fetch |
| pgvector | Complete — asyncpg, cosine/l2/ip auto-detect, HNSW/IVFFlat health checks |
| Pinecone | Planned |
| Milvus | Planned |

## Eval CSV Format

```csv
id,text,vector,relevant_ids
q001,example query,"[0.1, 0.2, ...]","doc-1,doc-2"
```

Required columns: `id` (or `query_id`/`qid`), `text` (or `query`), `vector`, `relevant_ids`.

## Development

```bash
make install-dev    # install all extras + dev deps
make test-unit      # run the unit test suite
make check          # ruff + mypy
make build-ui       # build the React UI into vara/server/static/
```

The React UI lives in `ui/`. Built assets are copied into `vara/server/static/`
and bundled into the Python wheel for single-binary distribution.
