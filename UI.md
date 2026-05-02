# Vara UI Plan

## Stack

| Concern | Choice | Reason |
|---------|--------|--------|
| Framework | React 18 + TypeScript | Already scaffolded |
| Build | Vite 5 | Already scaffolded |
| Styling | Tailwind CSS v3 | Utility-first, easy dark theme, no runtime overhead |
| Routing | React Router v6 | Panel-per-route, browser back/forward works |
| State | Zustand | Already scaffolded, extend existing store |
| Charts | Recharts | Already installed |
| 3D | @react-three/fiber + Three.js | Already installed |
| Icons | lucide-react | Clean, consistent, tree-shakeable |
| WebSocket | Native browser WebSocket | No extra dep needed |

**No component library** — custom components only. Keeps the design coherent and bundle small.

---

## Design Tokens

### Colors

```ts
// tailwind.config.ts extensions
colors: {
  bg: {
    base:    '#0F1117',   // app background
    surface: '#1A1D2E',   // cards, panels, sidebar
    raised:  '#232640',   // inputs, hover states, tooltips
    border:  '#2D3148',   // panel borders, dividers
  },
  accent: {
    DEFAULT: '#7C6AF7',   // indigo-violet — primary CTA, active nav, focus rings
    hover:   '#9585F8',
    muted:   '#3D3572',   // subtle tint backgrounds
  },
  text: {
    primary:  '#E2E8F0',
    secondary: '#94A3B8',
    muted:    '#64748B',
    code:     '#A5F3FC',  // cyan — IDs, raw vectors, SQL
  },
  severity: {
    error:   '#F87171',   // red-400
    warning: '#FBBF24',   // amber-400
    healthy: '#34D399',   // emerald-400
    info:    '#60A5FA',   // blue-400
  },
}
```

### Typography

```ts
fontFamily: {
  sans: ['Inter', 'system-ui', 'sans-serif'],   // UI chrome
  mono: ['JetBrains Mono', 'Fira Code', 'monospace'],  // vectors, IDs, SQL
}
fontSize: {
  xs:  '11px',
  sm:  '13px',
  base: '14px',
  lg:  '16px',
  xl:  '20px',
}
```

### Spacing & Shape

- Base unit: `4px` (Tailwind default)
- Card border radius: `rounded-lg` (8px)
- Input border radius: `rounded-md` (6px)
- Button border radius: `rounded-md` (6px)
- Panel gap: `16px`
- Sidebar width: `220px` (collapsed: `52px`)
- Box shadow: `shadow-lg` with `bg-border` color, no white glow

---

## Layout

```
┌─────────────────────────────────────────────────────────┐
│  TopBar  [Vara logo]  [backend selector]  [status dot]  │
├──────────┬──────────────────────────────────────────────┤
│          │                                              │
│ Sidebar  │           Panel Content Area                 │
│          │                                              │
│ • Debug  │  (routed per panel, fills remaining height)  │
│ • Health │                                              │
│ • Eval   │                                              │
│ • Explore│                                              │
│          │                                              │
└──────────┴──────────────────────────────────────────────┘
```

- TopBar: fixed, 48px tall
- Sidebar: fixed left, 220px, scrollable nav
- Content: `margin-left: 220px`, `margin-top: 48px`, fills viewport

### Routes

```
/               → redirect to /debug
/debug          → QueryDebugger
/health         → IndexHealth
/eval           → EvalRunner
/explore        → VectorExplorer
```

---

## Global State (Zustand)

Extend the existing store:

```ts
type VaraState = {
  // Backend/collection selection (already exists)
  backendName: string
  collectionName: string
  setBackendName: (name: string) => void
  setCollectionName: (name: string) => void

  // Available backends loaded from /api/config on mount
  backends: BackendStatus[]
  collections: CollectionInfo[]
  setBackends: (backends: BackendStatus[]) => void
  setCollections: (collections: CollectionInfo[]) => void
}
```

Backends and collections are fetched once on app mount and stored globally so every panel can read them via the sidebar selector.

---

## API Client (`src/api/client.ts`)

Already stubbed. Implement typed functions for every backend endpoint:

```ts
getConfig()                          → ConfigResponse
getCollections()                     → CollectionInfo[]
getHealth(backend, collection)       → HealthReport
debugQuery(req)                      → DebugQueryResponse
compareQuery(req)                    → CompareQueryResponse
diagnoseQuery(req)                   → DiagnoseResponse
startEval(req)                       → { job_id, total_queries }
connectEvalWS(job_id, onProgress, onComplete, onError)  → () => void (close fn)
connectProjectionWS(params, onBatch, onComplete, onError) → () => void (close fn)
```

All functions use `fetch` with `Content-Type: application/json`. WS helpers wrap native `WebSocket` and return a teardown function.

---

## Shared Components

```
src/components/
  layout/
    TopBar.tsx          — logo, backend/collection selectors, connection status dot
    Sidebar.tsx         — nav links with icons, active highlight in accent color
  ui/
    Card.tsx            — bg-surface border border-border rounded-lg p-4
    Badge.tsx           — severity-colored pill (error/warning/healthy/info)
    Button.tsx          — primary (accent bg) + ghost variant
    Input.tsx           — dark bg-raised border, cyan focus ring
    Spinner.tsx         — animated indigo ring
    EmptyState.tsx      — icon + message for empty results
    CodeBlock.tsx       — monospace, bg-raised, cyan text, copy button
    ScoreBar.tsx        — horizontal bar 0–1, accent fill, used for hit scores
  data/
    HitCard.tsx         — single QueryHit: id (mono), score bar, payload
    FindingCard.tsx     — single HealthFinding: severity badge, code, message, recommendation
```

---

## Panels

### 1. QueryDebugger (`/debug`)

**Purpose:** Run a vector query against one or two backends, inspect hits side by side.

**Layout:**
```
┌─ Query Input ──────────────────────────────────────────┐
│  [Vector textarea]  [top_k]  [filters JSON]            │
│  [backend checkboxes]        [Run Query button]         │
└────────────────────────────────────────────────────────┘
┌─ Mode tabs: [Debug] [Compare] [Diagnose] ──────────────┐
│                                                         │
│  Debug:   side-by-side hit lists per backend            │
│  Compare: Jaccard / Spearman stats + diff highlight     │
│  Diagnose: expected IDs input → per-doc finding cards   │
└────────────────────────────────────────────────────────┘
```

**State (local):**
- `vectorText: string` — raw JSON text from textarea
- `topK: number`
- `filtersText: string` — raw JSON
- `selectedBackends: string[]`
- `mode: 'debug' | 'compare' | 'diagnose'`
- `expectedIds: string` — comma-separated, diagnose mode only
- `result: DebugQueryResponse | CompareQueryResponse | DiagnoseResponse | null`
- `loading: boolean`
- `error: string | null`

**Key UX details:**
- Vector textarea accepts raw JSON array `[0.1, 0.2, ...]` — validated on submit
- Backend checkboxes auto-populated from global store
- Compare mode only enabled when exactly 2 backends selected
- Common hits highlighted in green, unique hits highlighted per backend
- Latency shown as `Xms` badge on each backend result header
- `native_query.sql` shown in a collapsible CodeBlock

---

### 2. IndexHealth (`/health`)

**Purpose:** Show health status for each backend/collection with actionable findings.

**Layout:**
```
┌─ Backend cards (one per backend) ─────────────────────┐
│  [●] local-qdrant   bench_vectors   healthy   [Check]  │
│      latency: 4ms                                       │
│                                                         │
│  [●] local-pgvector bench_vectors   degraded  [Check]  │
│      latency: 8ms                                       │
│      ⚠ no_vector_index — Create an HNSW index...       │
└────────────────────────────────────────────────────────┘
```

**State (local):**
- `reports: Record<string, HealthReport>` — keyed by backend name
- `loading: Record<string, boolean>`

**Key UX details:**
- Status dot: green (healthy) / amber (degraded) / red (unhealthy)
- Findings rendered as `FindingCard` components below each backend card
- "Check" button re-fetches health for that backend only
- "Check All" button in panel header re-fetches all in parallel
- Stats sub-section (collapsible): vector_count, dimension, disk_bytes, index_type

---

### 3. EvalRunner (`/eval`)

**Layout:**
```
┌─ Config ───────────────────────────────────────────────┐
│  dataset path  [____________________]                   │
│  backend       [dropdown]  k [___]                      │
│                            [Run Eval]                   │
└────────────────────────────────────────────────────────┘
┌─ Live Progress ────────────────────────────────────────┐
│  ndcg@k: 0.53  mrr@k: 1.0  recall@k: 0.40             │
│  p50: 18ms  p95: 34ms  p99: 51ms                       │
│  [===========================-------]  35/50 queries    │
│  [Recharts line chart — metrics over queries]           │
└────────────────────────────────────────────────────────┘
┌─ Results (after complete) ─────────────────────────────┐
│  final metrics table  +  [Export JSON]                  │
└────────────────────────────────────────────────────────┘
```

**State (local):**
- `datasetPath: string`
- `backend: string`
- `k: number`
- `jobId: string | null`
- `progress: EvalProgress[]` — accumulates WS events
- `status: 'idle' | 'running' | 'complete' | 'error'`

**Key UX details:**
- WS connection opened after `POST /api/eval/run` returns `job_id`
- Recharts `LineChart` streams metric values per query index
- Progress bar uses `processed / total_queries`
- Export button serialises final `EvalProgress[]` to JSON and triggers download
- WS closed automatically on complete or error

---

### 4. VectorExplorer (`/explore`)

**Layout:**
```
┌─ Controls ─────────────────────────────────────────────┐
│  IDs (comma-sep) [_______]  algo [UMAP|t-SNE]          │
│  n_neighbors [10]  min_dist [0.1]  [Project]           │
└────────────────────────────────────────────────────────┘
┌─ 3D Canvas (fills remaining height) ──────────────────┐
│                                                         │
│   @react-three/fiber point cloud                        │
│   - orbit controls (mouse drag to rotate)               │
│   - points colored by backend or cluster                │
│   - hover tooltip: id, score, payload snippet           │
│                                                         │
└─ [job progress bar while streaming] ───────────────────┘
```

**State (local):**
- `idsText: string`
- `params: ProjectionParams`
- `points: ProjectionPoint[]` — accumulated from WS batches
- `status: 'idle' | 'running' | 'complete' | 'error'`
- `hoveredId: string | null`

**Key UX details:**
- Three.js `Points` geometry rebuilt on each WS batch (incremental render)
- OrbitControls from `@react-three/drei` for pan/rotate/zoom
- Point color: accent indigo by default, red for any ID that appeared in a diagnose result
- Hover: raycaster picks nearest point, shows tooltip with id + payload
- "Add more IDs" button triggers incremental projection via `base_job_id`

---

## Implementation Order

1. **Install deps** — `tailwindcss`, `react-router-dom`, `lucide-react`, `@react-three/drei`
2. **Tailwind config** — extend with design tokens above
3. **Layout** — TopBar + Sidebar + router shell, backend/collection selector wired to store
4. **API client** — implement all typed functions in `client.ts`
5. **Shared components** — Card, Badge, Button, Input, CodeBlock, HitCard, FindingCard, ScoreBar
6. **IndexHealth panel** — simplest panel, good to validate component primitives
7. **QueryDebugger panel** — core feature, all three modes
8. **EvalRunner panel** — WS streaming + Recharts chart
9. **VectorExplorer panel** — Three.js point cloud + WS streaming

---

## File Structure (target)

```
ui/src/
  main.tsx
  App.tsx                    — router setup
  api/
    client.ts                — all API + WS helpers
    types.ts                 — TypeScript mirrors of backend Pydantic models
  store/
    index.ts                 — extended Zustand store
  components/
    layout/
      TopBar.tsx
      Sidebar.tsx
    ui/
      Card.tsx  Badge.tsx  Button.tsx  Input.tsx
      Spinner.tsx  EmptyState.tsx  CodeBlock.tsx  ScoreBar.tsx
    data/
      HitCard.tsx  FindingCard.tsx
  panels/
    QueryDebugger.tsx
    IndexHealth.tsx
    EvalRunner.tsx
    VectorExplorer.tsx
```
