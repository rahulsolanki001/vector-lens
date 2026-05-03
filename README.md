# Vara

**Vara is a debugging and observability tool for vector search systems.**

It helps you understand *why your RAG retrieval works—or fails* across different vector databases, index configurations, and query setups.  
Run queries, compare backends, diagnose failures, visualize embedding structure, and evaluate retrieval quality—all in one place.

---

## Why Vara?

Vector search failures are hard to debug. When a query gives poor results, the issue could be:

- bad embeddings  
- incorrect index configuration  
- query parameters  
- backend-specific behavior  

Vara helps you identify the root cause.

With Vara, you can:

- Compare retrieval results across multiple vector databases
- Diagnose why expected results were not retrieved
- Inspect index health and configuration issues
- Visualize vector space structure (clusters, overlaps, outliers)
- Run reproducible retrieval evaluations with real metrics

---

## Core Features

### Query Debugger

Understand and compare retrieval behavior across backends.

- **Debug mode**
  - Inspect per-backend results with latency, scores, and payloads

- **Compare mode**
  - Quantify differences between backends:
    - Jaccard similarity
    - Rank correlation (Spearman ρ)
    - Score correlation
  - Diff-highlighted result lists

- **Diagnose mode**
  - Explain *why expected results were not retrieved*:
    - not found
    - found but not retrieved
    - score gap from top results
  - Provides actionable recommendations

Helps answer: **“Why didn’t my query return what I expected?”**

---

### Index Health

Quickly identify misconfigurations and performance risks.

- Health status: **healthy / degraded / unhealthy**
- Detect issues such as:
  - missing HNSW index
  - empty collections
  - connectivity errors
- Detailed stats:
  - vector count
  - dimension
  - distance metric
  - index type
  - disk usage

Helps distinguish **index issues vs embedding issues**

---

### Eval Runner

Run reproducible retrieval benchmarks.

- Execute evaluation from CSV datasets
- Live streaming metrics via WebSocket:
  - nDCG@k
  - MRR@k
  - Recall@k
  - p50 / p95 / p99 latency
- Real-time charts (Recharts)
- Export results as JSON

Compare **quality and performance across backends and configs**

---

### Vector Explorer

Understand the structure of your embedding space.

- UMAP or t-SNE projection
- **2D and 3D modes**
- HDBSCAN clustering (auto-detect clusters + noise)
- Color by payload field or cluster
- Hover:
  - payload preview
  - nearest-neighbour connections
- Click:
  - full payload inspection in side panel
- Incremental projection (“Add More IDs”)
- HUD: point count, algorithm, dimension, timing

Helps explain **why certain results are retrieved (or missed)**

---

## Typical Workflow

1. Run a query in **Query Debugger**
2. Notice unexpected or missing results
3. Use **Diagnose mode** to identify the issue
4. Inspect vector structure in **Vector Explorer**
5. Check index configuration in **Index Health**
6. Validate improvements using **Eval Runner**

---

## Quick Start

```bash
pip install -e ".[qdrant,pgvector,dev]"
cp vara.yaml.example vara.yaml

# Start local services
docker compose -f docker-compose.dev.yml up -d

# Start backend + UI
vara dev

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
