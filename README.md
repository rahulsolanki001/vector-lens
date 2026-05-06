# Vara

**Vara is a debugging and observability tool for vector search systems.**

It helps you understand *why your RAG retrieval works—or fails* across different vector databases, index configurations, and query setups.  
Run queries, compare backends, diagnose failures, visualize embedding structure, and evaluate retrieval quality—all in one place.

---

## Why Vara?

Vector search failures are hard to debug. When a query gives poor results, the issue could be bad embeddings, incorrect index configuration, wrong query parameters, or backend-specific behavior.

With Vara, you can:

- Compare retrieval results across multiple vector databases simultaneously
- Diagnose why expected results were not retrieved, with a classified root-cause verdict
- Inspect index health, configuration risks, and live stats for all backends at once
- Visualize your embedding space in 2D/3D with UMAP or t-SNE and HDBSCAN clustering
- Run reproducible retrieval evaluations with streaming metrics and real-time charts

---

## Core Features

### Query Debugger

Understand and compare retrieval behavior across backends.

**Debug mode**
- Inspect per-backend results with latency, scores, and payloads
- Run against 1–4 backends simultaneously in an N-column grid
- "View in Explorer" — jump directly to Vector Explorer with all result IDs pre-loaded

**Compare mode**
- Side-by-side diff across 2–4 backends with:
  - Jaccard similarity
  - Rank correlation (Spearman ρ)
  - Score correlation
- Result diff table: ID, rank in A/B, Δ rank, score in A/B, Δ score, missing flag

**Diagnose mode**
- Explain *why expected results were not retrieved*:
  - not found in the index
  - found but ranked too low to be retrieved
  - score gap from the top results
- **Verdict banner** — classifies the dominant root cause: not in index, filter exclusion, embedding mismatch, or weak semantic match
- Per-query ground truth metrics (Recall@k, MRR) shown as tiles
- "View in Explorer" — jump to Vector Explorer with retrieved + expected IDs pre-loaded

---

### Index Health

Quickly identify misconfigurations and performance risks across all backends.

- Health status: **healthy / degraded / unhealthy** per backend
- Runs checks in parallel — one card per backend in an auto-fill responsive grid
- Adapter-specific checks:
  - **Qdrant** — segment health, optimizer state, payload index coverage
  - **pgvector** — extension present, HNSW/IVFFlat index, empty table
  - **Milvus** — load state, index present, HNSW `efConstruction`/`M`, IVF `nlist` sanity
  - **Pinecone** — index ready state, fullness (warn >75%, error >90%)
- Live stats per collection: vector count, dimension, distance metric, disk/RAM usage

---

### Eval Runner

Run reproducible retrieval benchmarks with a live telemetry dashboard.

Three dataset sources:

- **CSV** — `id, text, vector, relevant_ids` columns with flexible field aliases
- **JSON / JSONL** — array of objects or one object per line
- **Collection sample** — samples N random vectors from the live index for a self-retrieval sanity check (no file needed)

Live streaming metrics (WebSocket):

- nDCG@k, MRR@k, Recall@k (running means, updated per query)
- p50 / p95 / p99 latency percentiles
- Real-time sparkline chart (nDCG + MRR traces)
- Proportional latency bars (p50 / p95 / p99)

---

### Vector Explorer

Understand the structure of your embedding space.

- UMAP or t-SNE dimensionality reduction
- **2D and 3D projection modes** — toggle without re-projecting
- HDBSCAN clustering — auto-detect clusters and noise points
- Color by payload field or cluster assignment
- Hover: payload preview + nearest-neighbour connection lines
- Click: full payload inspection in a slide-up drawer
- Incremental projection ("Add More IDs") — extend an existing projection without re-running UMAP from scratch
- HUD overlay: point count, algorithm, projection dimensions, timing
- **Jump from Query Debugger** — "View in Explorer" seeds IDs and auto-projects on arrival
- Three.js point cloud with bloom post-processing

---

## Typical Workflow

1. Run a query in **Query Debugger**
2. Notice unexpected or missing results
3. Switch to **Diagnose mode** — read the verdict banner for the likely root cause
4. Click **"View in Explorer"** — jump to Vector Explorer with result IDs pre-loaded
5. Check index configuration in **Index Health**
6. Validate improvements using **Eval Runner**

---

## Quick Start

```bash
# Install with the adapters you need
pip install -e ".[qdrant,pgvector,milvus,pinecone,dev]"

cp vara.yaml.example vara.yaml
# Edit vara.yaml to point at your backends

# Start local services (Qdrant, pgvector, Milvus)
docker compose -f docker-compose.dev.yml up -d

# Start backend + UI with hot-reload
vara dev
```

Then open [http://localhost:5173](http://localhost:5173).

For production use:

```bash
vara serve          # starts the API + serves the built React UI
```

---

## Configuration

```yaml
# vara.yaml

vara:
  port: 7842
  open_browser: true
  log_level: info

backends:

  - name: local-qdrant
    type: qdrant
    host: localhost
    port: 6333

  - name: local-pgvector
    type: pgvector
    dsn: postgresql://vara:vara@localhost:5432/vara
    table: embeddings
    vector_column: embedding

  - name: local-milvus
    type: milvus
    host: localhost
    port: 19530
    default_collection: my_collection

  - name: my-pinecone
    type: pinecone
    api_key: ${PINECONE_API_KEY}
    index: my-index
    namespace: ""          # optional; leave empty for the default namespace
```

Environment variables are interpolated using `${VAR}` syntax anywhere in `vara.yaml`.

---

## CLI

```bash
vara serve          # start the API server (opens browser automatically)
vara dev            # server + Vite hot-reload for UI development
vara check          # print a live health table for all configured backends
vara eval           # run a retrieval eval from a dataset file and write JSON results
```

---

## Adapters

| Backend | Status | Notes |
|---------|--------|-------|
| Qdrant | Complete | query, health, stats, filters, vector fetch, grpc support |
| pgvector | Complete | asyncpg, cosine/l2/ip auto-detect from `pg_indexes`, HNSW/IVFFlat health |
| Milvus | Complete | pymilvus 2.4 MilvusClient, Zilliz Cloud, HNSW/IVF health, load-state checks |
| Pinecone | Complete | SDK v3+, serverless and pod specs, fullness/readiness health checks |

---

## Eval Dataset Formats

**CSV**
```csv
id,text,vector,relevant_ids
q001,example query,"[0.1, 0.2, ...]","doc-1,doc-2"
```

**JSON** (array or JSONL)
```json
[
  {
    "id": "q001",
    "text": "example query",
    "vector": [0.1, 0.2],
    "relevant_ids": ["doc-1", "doc-2"]
  }
]
```

Accepted field aliases:

| Field | Aliases |
|-------|---------|
| `id` | `query_id`, `qid` |
| `text` | `query` |
| `vector` | `embedding` |
| `relevant_ids` | `doc_ids`, `expected_ids` |

**Collection sample** — no file needed. Select a backend and collection in the Eval Runner UI, set `n_samples`, and Vara fetches live vectors from your index for a self-retrieval sanity check.

---

## Development

```bash
make install-dev    # install all extras + dev deps
make test-unit      # run the unit test suite
make check          # ruff + mypy
make build-ui       # build the React UI into vara/server/static/
make build          # build UI assets + Python wheel/sdist
```

The React UI lives in `ui/`. Built assets are copied into `vara/server/static/` and bundled into the Python wheel for single-command distribution (`vara serve`).

## Packaging

```bash
make clean
make build
python3 -m venv /tmp/vara-wheel-check
/tmp/vara-wheel-check/bin/pip install dist/vara-*.whl
/tmp/vara-wheel-check/bin/vara --help
```

Release builds should be created after the UI is built, because the wheel
includes the compiled React assets from `vara/server/static/`.
