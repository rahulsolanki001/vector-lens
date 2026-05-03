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
| Post-processing | @react-three/postprocessing | ✅ installed |
| Icons | lucide-react | ✅ installed |
| Fonts | geist (npm, self-hosted variable woff2) | ✅ installed |
| WebSocket | Native browser WebSocket | no dep needed |

**No component library** — custom components only. Keeps the design coherent and bundle small.

---

## Design Tokens

### Colors

Token names are unchanged so all components continue to work without edits. Only the hex values were updated to the ink scale.

```ts
colors: {
  bg: {
    base:    '#0B0D12',              // app background (near-black)
    surface: '#11141B',              // cards, panels, sidebar
    raised:  '#161A22',              // inputs, hover states
    border:  '#1F2330',              // dividers, borders
  },
  accent: {
    DEFAULT: '#8B7DFF',              // violet — primary CTA, active states
    hover:   '#9D90FF',
    muted:   'rgba(139,125,255,0.14)', // transparent tint for hover/focus
  },
  cy: {
    DEFAULT: '#5DE3FF',              // cyan — second accent, code text
    soft:    'rgba(93,227,255,0.12)',
  },
  tx: {
    primary:   '#ECEDEF',            // warm off-white (not pure white)
    secondary: '#A8AEBB',
    muted:     '#6E7689',
    code:      '#5DE3FF',            // cyan — IDs, vectors, SQL (= cy.DEFAULT)
  },
  sev: {
    error:   '#F47272',
    warning: '#F2B45A',
    healthy: '#5BD6A8',
    info:    '#7AB8FF',
  },
}
```

CSS custom properties (`:root`):
```css
--grad:     linear-gradient(135deg, #8B7DFF 0%, #5DE3FF 100%);
--vio-soft: rgba(139, 125, 255, 0.14);
--cy-soft:  rgba(93, 227, 255, 0.12);
```

Used directly in components where Tailwind utility classes can't express the value (gradient fills, conic rings, glow shadows).

### Typography

```ts
fontFamily: {
  sans:  ['Geist', 'Inter', 'system-ui', 'sans-serif'],
  mono:  ['Geist Mono', 'JetBrains Mono', 'monospace'],
  serif: ['Instrument Serif', 'Georgia', 'serif'],   // wordmark only
}
fontSize: {
  xs:   ['11px', { lineHeight: '16px', letterSpacing: '0.04em' }],
  sm:   ['12px', { lineHeight: '18px' }],
  base: ['13px', { lineHeight: '20px' }],
  lg:   ['16px', { lineHeight: '24px' }],
  xl:   ['22px', { lineHeight: '28px' }],
}
```

- Geist and Geist Mono are self-hosted variable woff2 files from the `geist` npm package, served from `public/fonts/`. No Google Fonts dependency for body text.
- Instrument Serif loaded via Google Fonts (`@import` in `index.css`) — used only for the wordmark.
- Body size tightened to 13px (was 14px) — denser feels more devtool-appropriate.

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
    TopBar.tsx          — logo + connection status dot (backend/collection selection is panel-local)
    Sidebar.tsx         — nav links with icons, active highlight in accent color
  ui/
    Card.tsx            — bg-surface border rounded-lg, inset top-edge highlight
    Badge.tsx           — colored dot + mono text; variants: error/warning/info/healthy/degraded/unhealthy/vio/cy/default
    Button.tsx          — primary (gradient + glow shadow + inset highlight + kbd hint slot) + ghost
    Input.tsx           — kicker label (mono uppercase), vio focus ring; exports Input, Textarea, Select
    Spinner.tsx         — animated accent ring
    EmptyState.tsx      — icon tile with radial glow + readable sub-text
    CodeBlock.tsx       — bg-base (deeper), cyan text, 11.5px mono, copy button
    ScoreBar.tsx        — 4px bar, --grad fill, scaleX mount animation
    SegmentedControl.tsx — tab/mode switcher; active segment has inset shadow
    Kicker.tsx          — mono uppercase 11px tracking label for section headers
  data/
    HitCard.tsx         — compact row: rank (color-coded) · id + payload preview · score + ScoreBar;
                          2px left border for common (green) / unique (violet) highlight
    FindingCard.tsx     — severity icon + badge + code + message + recommendation
```

---

## Panels

### 1. QueryDebugger (`/debug`)

**Purpose:** Run a vector query against 1–4 backends, inspect hits side by side, compare or diagnose retrieval.

**Layout:**
```
┌─ Input column (380px, sticky) ──┬─ Results column (flex-1, scrolls) ──┐
│  [title]  [Debug|Compare|Diagnose]  │                                       │
│                                  │  Debug:   stats strip + N-col hit grid   │
│  VECTOR                          │  Compare: similarity tiles (pairwise) or │
│  [textarea]                      │           stats strip (N-way) + diff     │
│                                  │           table + N hit columns           │
│  BACKENDS                        │  Diagnose: verdict banner + truth tiles  │
│  [chip] [chip] [chip]            │           + per-doc cards                │
│                                  │                                           │
│  COLLECTION                      │                                           │
│  [select]                        │                                           │
│                                  │                                           │
│  TOP-K          [slider]  [10]   │                                           │
│                                  │                                           │
│  FILTERS (JSON, optional)        │                                           │
│  [textarea]                      │                                           │
│                                  │                                           │
│  [Run ↵]                         │                                           │
│                                  │                                           │
│  NATIVE QUERY (after first run)  │                                           │
│  [CodeBlock]                     │                                           │
└──────────────────────────────────┴───────────────────────────────────────────┘
```

**State (local):**
- `vectorText: string` — raw JSON text from textarea
- `topK: number` — driven by slider (1–100)
- `filtersText: string` — raw JSON
- `selectedBackends: string[]`
- `collectionName: string` — panel-local (not from global store)
- `mode: 'debug' | 'compare' | 'diagnose'`
- `expectedIds: string` — comma-separated, diagnose mode only
- `result: DebugQueryResult | BackendComparison | DiagnosisResult | null`
- `loading: boolean`
- `error: string | null`

**Key UX details:**
- Two-column sticky layout — input always visible while results scroll
- Mode switcher is a `SegmentedControl`; compare enabled when ≥ 2 backends selected
- Backend selectors are chip-buttons with active violet tint + inline type tag
- Top-K uses a range slider with live mono value display
- Field labels use `Kicker` component (mono uppercase)
- Native query preview (`CodeBlock`) pinned to bottom of input column, appears after first run
- **Debug mode**: stats strip (latency + hit count per backend); grid adapts 1→2→3→4 columns; `HitCard` rows with color-coded rank, payload preview, score + ScoreBar
- **Compare mode (2 backends)**: calls `compareQuery`; Jaccard, rank ρ, score ρ, common-hits tiles; N-way diff table (best rank = green, worst = amber, spread column); side-by-side hit lists
- **Compare mode (3–4 backends)**: calls `debugQuery`; stats strip instead of pairwise metrics; same N-way diff table generalised to N columns
- **HitCard highlight**: 2px left border — `border-sev-healthy` for common hits, `border-accent` for unique-to-this-backend
- **Diagnose mode**: amber gradient verdict banner with icon tile; three truth tiles (Recall@k / MRR / Hits) each with a conic-gradient donut ring; per-doc rank badges color-coded (green ≤3, amber ≤8, red otherwise)
- **"View in Explorer" button**: appears on debug and diagnose results; seeds `explorerSeedIds` in store and navigates to `/explore`

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
| 18 | UI redesign R0 — ink palette, Geist fonts, CSS vars, ::selection, focus ring | ✅ done |
| 19 | UI redesign R1 — full component library upgrade (Button, Badge, ScoreBar, CodeBlock, Card, Input, EmptyState, Spinner, SegmentedControl, Kicker) | ✅ done |
| 20 | UI redesign R2 — QueryDebugger two-column workbench, N-backend compare, HitCard row redesign | ✅ done |
| 21 | UI redesign R3 — Index Health grid | ⬜ |
| 22 | UI redesign R4 — Eval Runner live dashboard + sparkline | ⬜ |
| 23 | UI redesign R5 — Vector Explorer glass overlays + Three.js dramatic mode | ⬜ |
| 24 | UI redesign R6 — empty states + copy pass | ⬜ |

### Notes
- Pinned `@react-three/drei@^9` (not v10) — fiber v8 requires React 18; drei v10 requires fiber v9 + React 19
- Tailwind color keys: `bg-*`, `accent-*`, `tx-*`, `sev-*`, `cy-*` — token names unchanged from original; only values updated
- Geist + Geist Mono: variable woff2 files copied from `geist` npm package to `public/fonts/`, loaded via `@font-face` in `index.css`; preloaded in `index.html`
- Instrument Serif: loaded via Google Fonts for wordmark use only
- TopBar: logo + connection status dot only; backend/collection selection is panel-local in each panel
- Global store (`store/index.ts`): `backendName`/`collectionName`/`setBackendName`/`setCollectionName` removed; each panel manages its own selection with local `useState`
- `SegmentedControl` is generic over `T extends string` — works for any set of string options
- `Kicker` renders `font-mono text-xs uppercase tracking-[0.08em] text-tx-muted` — use for all section headers
- Compare mode: 2 backends → `compareQuery` (Spearman ρ available); 3–4 backends → `debugQuery` (no Spearman, but N-way diff table still works via `HitAlignment.ranks: Record<string,number>`)
- VectorExplorer geometry: fully imperative `primitive` approach with coordinate normalisation; declarative `bufferAttribute args` does not update in r3f v8

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
