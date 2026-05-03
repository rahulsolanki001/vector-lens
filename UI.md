# Vara UI Plan

## Stack

| Concern | Choice | Status |
|---------|--------|--------|
| Framework | React 18 + TypeScript | ✅ installed |
| Build | Vite 5 | ✅ installed |
| Styling | Tailwind CSS v3 | ✅ installed + configured |
| Routing | React Router v6 (react-router-dom v7) | ✅ installed |
| State | Zustand | ✅ installed |
| Charts | Recharts | ✅ installed |
| 3D | @react-three/fiber v8 + @react-three/drei v9 + Three.js | ✅ installed |
| Icons | lucide-react | ✅ installed |
| WebSocket | Native browser WebSocket | no dep needed |

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
  // Backend/collection selection
  backendName: string
  collectionName: string
  setBackendName: (name: string) => void
  setCollectionName: (name: string) => void

  // Available backends loaded from /api/config on mount
  backends: BackendStatus[]
  collections: CollectionInfo[]
  setBackends: (backends: BackendStatus[]) => void
  setCollections: (collections: CollectionInfo[]) => void

  // Explorer jump seed — set by QueryDebugger, consumed by VectorExplorer on mount
  explorerSeedIds: string[]
  explorerSeedBackend: string
  setExplorerSeed: (ids: string[], backend: string) => void
  clearExplorerSeed: () => void
}
```

Backends and collections are fetched once on app mount and stored globally so every panel can read them via the sidebar selector. The explorer seed fields are written by QueryDebugger and cleared by VectorExplorer on arrival.

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
- **Compare mode**: result diff table shows ID, rank A/B, Δ rank, score A/B, Δ score, missing flag for every hit across both backends
- **Diagnose mode**: amber verdict banner classifies the dominant root cause (not in index / filter exclusion / embedding mismatch / low rank)
- **"View in Explorer" button**: appears on debug results (all hit IDs) and diagnose results (retrieved + expected IDs); seeds `explorerSeedIds` in store and navigates to `/explore`
- **Diagnose mode ground truth tiles**: three metric tiles (`Recall@k`, `MRR`, `Hits N/M`) appear between the Summary card and per-document list whenever `expected_ids` are provided; computed by the backend in `diagnose_retrieval()` and added to `DiagnosisResult`

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
│  n_neighbors [10]  min_dist [0.1]  color-by [field]    │
│  [Project]  [Add More IDs]                              │
└────────────────────────────────────────────────────────┘
┌─ 3D Canvas (fills remaining height) ──────────────────┐
│                                                         │
│   Bloom/glow post-processing (EffectComposer)           │
│   Points colored by payload field (palette per group)   │
│   Auto-rotate when idle, stops on user drag             │
│   Click to select → side detail panel                   │
│   Hover → K nearest-neighbour lines in projected space  │
│   HUD overlay: point count, algorithm, elapsed time     │
│                                                         │
│  ┌─ Selected point drawer (right side, slide-in) ─────┐ │
│  │  ID (mono)  payload fields  [Deselect]             │ │
│  └────────────────────────────────────────────────────┘ │
└─ Color legend (bottom-left)  ─ progress bar ───────────┘
```

**State (local):**
- `idsText: string`
- `params: ProjectionParams`
- `points: ProjectionPoint[]` — accumulated from WS batches
- `status: 'idle' | 'running' | 'complete' | 'error'`
- `hoveredId: string | null`
- `selectedId: string | null` — clicked/locked point
- `colorByField: string` — payload field used for group coloring
- `groupColorMap: Record<string, string>` — derived palette per unique field value

**Key UX details:**
- Geometry: fully imperative `THREE.Points` via `<primitive>`, coordinates normalised to `[-2, 2]` cube; camera auto-fit to bounding sphere on first render
- OrbitControls for pan/rotate/zoom; auto-rotate (`autoRotate`) when idle, paused on pointer-down
- **Bloom**: `@react-three/postprocessing` `EffectComposer` + `Bloom` pass — points glow with luminanceThreshold tuned to accent colors
- **Payload coloring**: derive unique values of `colorByField` from loaded points, assign a color from a fixed palette (indigo, emerald, amber, sky, rose, violet…); fallback to accent indigo if field absent
- **Color legend**: bottom-left overlay listing group → color swatches
- **Hover**: raycaster picks nearest point, shows tooltip (id + 3 payload fields); draws `THREE.LineSegments` to K=5 nearest neighbours in projected space
- **Click to select**: locks point, slides in right-side detail panel with full payload; selected point rendered larger + white ring
- **HUD**: top-right corner overlay — point count, algorithm name, projection elapsed time
- **"Add more IDs"** button triggers incremental projection via `base_job_id`
- **2D/3D toggle**: `n_components` wired through to backend; 2D disables orbit rotate and auto-rotate
- **HDBSCAN clustering**: `POST /api/projection/{job_id}/cluster`; color-by-cluster mode with noise points in gray
- **Explorer jump (from QueryDebugger)**: if `explorerSeedIds` is set in store on mount, `idsText` and `backendName` are pre-populated and projection fires automatically; seed is cleared after consumption

**New dependency:** `@react-three/postprocessing` (wraps `postprocessing` library, compatible with fiber v8)

---

## Implementation Progress

| Step | Task | Status |
|------|------|--------|
| 1 | Install deps (`tailwindcss`, `react-router-dom`, `lucide-react`, `@react-three/drei`) | ✅ done |
| 2 | Tailwind config + design tokens + `index.css` + font import | ✅ done |
| 3 | Layout — TopBar + Sidebar + router shell, store wired to backend/collection selector | ✅ done |
| 4 | API client — typed functions + WS helpers in `client.ts`, `types.ts` | ✅ done |
| 5 | Shared components — Card, Badge, Button, Input, CodeBlock, HitCard, FindingCard, ScoreBar | ✅ done |
| 6 | IndexHealth panel | ✅ done |
| 7 | QueryDebugger panel (debug + compare + diagnose modes) | ✅ done |
| 8 | EvalRunner panel (WS streaming + Recharts chart) | ✅ done |
| 9 | VectorExplorer panel (Three.js point cloud + WS streaming) | ✅ done |
| 10 | VectorExplorer enhancements — bloom, payload coloring, click-select, neighbour lines, auto-rotate, HUD, color legend | ✅ done |
| 11 | VectorExplorer — 2D/3D toggle, t-SNE perplexity clamp | ✅ done |
| 12 | VectorExplorer — HDBSCAN clustering, color-by-cluster mode | ✅ done |
| 13 | EvalRunner — multi-source input: CSV, JSON/JSONL, Collection sample | ✅ done |
| 14 | QueryDebugger — result diff table (compare mode) | ✅ done |
| 15 | QueryDebugger — verdict banner (diagnose mode) | ✅ done |
| 16 | QueryDebugger → VectorExplorer jump via Zustand seed + auto-project | ✅ done |
| 17 | QueryDebugger — ground truth metric tiles (Recall@k, MRR, Hits) in diagnose mode | ✅ done |

### Notes
- Pinned `@react-three/drei@^9` (not v10) — fiber v8 requires React 18; drei v10 requires fiber v9 + React 19
- Tailwind color keys: `bg-*`, `accent-*`, `tx-*`, `sev-*` (not `text-*`/`severity-*` to avoid conflicts)
- Google Fonts loaded in `index.css`: Inter (400/500/600) + JetBrains Mono (400/500)
- TopBar height bumped to `h-16` (64px), logo `text-2xl font-bold`, sidebar items `py-3 text-base`
- Step 3 files: `Layout.tsx`, `TopBar.tsx`, `Sidebar.tsx`, updated `App.tsx`, `store/index.ts`
- Step 4 files: `api/types.ts` (13 interface groups), `api/client.ts` (all REST + 2 WS helpers)
- WS helpers return a teardown `() => void` — callers close on unmount or completion
- Step 5 files: `components/ui/` — Card, Badge, Button, Input (+ Textarea + Select), Spinner, EmptyState, CodeBlock, ScoreBar; `components/data/` — HitCard (rank + score bar + collapsible payload, common/unique highlight), FindingCard (severity icon + badge + code + message + recommendation)
- Steps 6–9: all panels complete and verified against live Qdrant + pgvector backends
- VectorExplorer geometry: fully imperative `primitive` approach with coordinate normalisation; declarative `bufferAttribute args` does not update in r3f v8
- Step 10 planned: bloom post-processing (`@react-three/postprocessing`), payload-field color grouping, click-to-select side panel, K nearest-neighbour hover lines, auto-rotate, HUD overlay, color legend

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
