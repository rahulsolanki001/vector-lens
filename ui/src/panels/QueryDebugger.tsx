import { useState, useCallback } from "react";
import { Play, ChevronDown, ChevronRight, AlertTriangle } from "lucide-react";
import type {
  DebugQueryResult,
  BackendComparison,
  DiagnosisResult,
  QueryResult,
  HitAlignment,
} from "../api/types";
import { debugQuery, compareQuery, diagnoseQuery } from "../api/client";
import { useVaraStore } from "../store";
import { Card } from "../components/ui/Card";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Input, Textarea } from "../components/ui/Input";
import { Spinner } from "../components/ui/Spinner";
import { EmptyState } from "../components/ui/EmptyState";
import { CodeBlock } from "../components/ui/CodeBlock";
import { HitCard } from "../components/data/HitCard";
import { FindingCard } from "../components/data/FindingCard";

// ── Types ─────────────────────────────────────────────────────────────────────

type Mode = "debug" | "compare" | "diagnose";
type AnyResult = DebugQueryResult | BackendComparison | DiagnosisResult | null;

// ── Mode tabs ─────────────────────────────────────────────────────────────────

function ModeTabs({
  mode,
  onChange,
  canCompare,
}: {
  mode: Mode;
  onChange: (m: Mode) => void;
  canCompare: boolean;
}) {
  const tabs: { id: Mode; label: string; disabled?: boolean }[] = [
    { id: "debug",    label: "Debug" },
    { id: "compare",  label: "Compare", disabled: !canCompare },
    { id: "diagnose", label: "Diagnose" },
  ];

  return (
    <div className="flex gap-1 p-1 bg-bg-raised rounded-lg w-fit">
      {tabs.map((t) => (
        <button
          key={t.id}
          disabled={t.disabled}
          onClick={() => !t.disabled && onChange(t.id)}
          className={`px-4 py-1.5 rounded-md text-sm font-medium transition-colors ${
            mode === t.id
              ? "bg-accent text-white"
              : t.disabled
              ? "text-tx-muted cursor-not-allowed opacity-40"
              : "text-tx-secondary hover:text-tx-primary hover:bg-bg-border"
          }`}
        >
          {t.label}
        </button>
      ))}
    </div>
  );
}

// ── Native query collapsible ──────────────────────────────────────────────────

function NativeQuery({ native }: { native: Record<string, unknown> }) {
  const [open, setOpen] = useState(false);
  const code = JSON.stringify(native, null, 2);
  return (
    <div className="mt-3 pt-3 border-t border-bg-border">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-1 text-xs text-tx-muted hover:text-tx-secondary transition-colors"
      >
        {open ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
        native query
      </button>
      {open && <div className="mt-2"><CodeBlock code={code} maxHeight="200px" /></div>}
    </div>
  );
}

// ── Debug mode results ────────────────────────────────────────────────────────

function DebugResults({ result }: { result: DebugQueryResult }) {
  const commonIds = new Set(result.common_hit_ids);

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
      {result.results.map((br) => (
        <Card key={br.backend_name}>
          <div className="flex items-center justify-between mb-3">
            <span className="text-sm font-semibold text-tx-primary">{br.backend_name}</span>
            <Badge variant="info">{br.result.latency_ms.toFixed(1)}ms</Badge>
          </div>
          <div className="flex flex-col gap-2">
            {br.result.hits.map((hit, i) => (
              <HitCard
                key={hit.id}
                hit={hit}
                rank={i + 1}
                highlight={commonIds.has(hit.id) ? "common" : "unique"}
              />
            ))}
            {br.result.hits.length === 0 && (
              <p className="text-xs text-tx-muted py-4 text-center">No hits returned</p>
            )}
          </div>
          <NativeQuery native={br.result.native_query} />
        </Card>
      ))}
      {result.errors.map((e) => (
        <Card key={e.backend_name}>
          <p className="text-sm font-semibold text-tx-primary mb-1">{e.backend_name}</p>
          <p className="text-xs text-sev-error">{e.error}</p>
        </Card>
      ))}
    </div>
  );
}

// ── Result diff table ─────────────────────────────────────────────────────────

interface DiffRow {
  id: string;
  rankA: number | null;
  rankB: number | null;
  scoreA: number | null;
  scoreB: number | null;
  delta: number | null;      // rank_a - rank_b; negative = A ranks higher
  scoreDiff: number | null;  // score_a - score_b
  missingFrom: string[];
}

function buildDiffRows(
  alignments: HitAlignment[],
  backendA: string,
  backendB: string,
): DiffRow[] {
  return alignments
    .map((a) => {
      const rankA  = a.ranks[backendA]  ?? null;
      const rankB  = a.ranks[backendB]  ?? null;
      const scoreA = a.scores[backendA] ?? null;
      const scoreB = a.scores[backendB] ?? null;
      return {
        id: a.id,
        rankA,
        rankB,
        scoreA,
        scoreB,
        delta:     rankA  !== null && rankB  !== null ? rankA  - rankB  : null,
        scoreDiff: scoreA !== null && scoreB !== null ? scoreA - scoreB : null,
        missingFrom: a.missing_from,
      };
    })
    .sort((a, b) => {
      const aMissing = a.missingFrom.length > 0;
      const bMissing = b.missingFrom.length > 0;
      if (aMissing !== bMissing) return aMissing ? 1 : -1;
      return (a.rankA ?? a.rankB ?? Infinity) - (b.rankA ?? b.rankB ?? Infinity);
    });
}

function DiffTable({
  alignments,
  backendA,
  backendB,
}: {
  alignments: HitAlignment[];
  backendA: string;
  backendB: string;
}) {
  const rows = buildDiffRows(alignments, backendA, backendB);
  if (rows.length === 0) return null;

  return (
    <Card>
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-tx-primary">Result Diff</h3>
        <span className="text-xs text-tx-muted font-mono">
          A = {backendA} · B = {backendB}
        </span>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-xs font-mono border-collapse">
          <thead>
            <tr className="border-b border-bg-border">
              <th className="text-left py-2 pr-4 text-tx-muted font-medium">ID</th>
              <th className="text-right py-2 px-3 text-tx-muted font-medium">rank A</th>
              <th className="text-right py-2 px-3 text-tx-muted font-medium">rank B</th>
              <th className="text-right py-2 px-3 text-tx-muted font-medium">Δ rank</th>
              <th className="text-right py-2 px-3 text-tx-muted font-medium">score A</th>
              <th className="text-right py-2 px-3 text-tx-muted font-medium">score B</th>
              <th className="text-right py-2 px-3 text-tx-muted font-medium">Δ score</th>
              <th className="text-left py-2 pl-3 text-tx-muted font-medium">missing</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr
                key={row.id}
                className={`border-b border-bg-border last:border-0 hover:bg-bg-raised transition-colors ${
                  row.missingFrom.length > 0 ? "opacity-50" : ""
                }`}
              >
                <td className="py-2 pr-4 text-tx-code max-w-[180px] truncate">{row.id}</td>
                <td className="py-2 px-3 text-right text-tx-secondary">{row.rankA ?? "—"}</td>
                <td className="py-2 px-3 text-right text-tx-secondary">{row.rankB ?? "—"}</td>
                <td className={`py-2 px-3 text-right font-semibold ${
                  row.delta === null ? "text-tx-muted" :
                  row.delta < 0      ? "text-sev-info" :
                  row.delta > 0      ? "text-sev-warning" :
                                       "text-tx-muted"
                }`}>
                  {row.delta === null
                    ? "—"
                    : row.delta > 0
                      ? `+${row.delta}`
                      : String(row.delta)}
                </td>
                <td className="py-2 px-3 text-right text-tx-secondary">{row.scoreA?.toFixed(4) ?? "—"}</td>
                <td className="py-2 px-3 text-right text-tx-secondary">{row.scoreB?.toFixed(4) ?? "—"}</td>
                <td className={`py-2 px-3 text-right font-semibold ${
                  row.scoreDiff === null      ? "text-tx-muted" :
                  row.scoreDiff >  0.0001     ? "text-sev-info" :
                  row.scoreDiff < -0.0001     ? "text-sev-warning" :
                                                "text-tx-muted"
                }`}>
                  {row.scoreDiff === null
                    ? "—"
                    : row.scoreDiff > 0
                      ? `+${row.scoreDiff.toFixed(4)}`
                      : row.scoreDiff.toFixed(4)}
                </td>
                <td className="py-2 pl-3">
                  {row.missingFrom.length > 0
                    ? <span className="text-sev-error">{row.missingFrom.join(", ")}</span>
                    : <span className="text-tx-muted">—</span>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="mt-3 pt-3 border-t border-bg-border flex gap-5 text-xs text-tx-muted">
        <span><span className="text-sev-info">Δ–</span> A ranks / scores higher</span>
        <span><span className="text-sev-warning">Δ+</span> B ranks / scores higher</span>
      </div>
    </Card>
  );
}

// ── Compare mode results ──────────────────────────────────────────────────────

function CompareResults({ result }: { result: BackendComparison }) {
  const debug = result.debug;
  const commonIds = new Set(debug.common_hit_ids);
  const uniqueA = new Set(debug.unique_hit_ids_by_backend[result.backend_a] ?? []);
  const uniqueB = new Set(debug.unique_hit_ids_by_backend[result.backend_b] ?? []);

  const resultByBackend: Record<string, QueryResult> = {};
  debug.results.forEach((r) => { resultByBackend[r.backend_name] = r.result; });

  function highlight(backendName: string, id: string): "common" | "unique" | undefined {
    if (commonIds.has(id)) return "common";
    if (backendName === result.backend_a && uniqueA.has(id)) return "unique";
    if (backendName === result.backend_b && uniqueB.has(id)) return "unique";
    return undefined;
  }

  return (
    <div className="flex flex-col gap-4">
      {/* Similarity stats */}
      <Card>
        <h3 className="text-sm font-semibold text-tx-primary mb-3">Similarity Metrics</h3>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          {[
            { label: "Jaccard",        value: result.jaccard_similarity.toFixed(4) },
            { label: "Rank ρ",         value: result.rank_spearman?.toFixed(4) ?? "—" },
            { label: "Score ρ",        value: result.score_spearman?.toFixed(4) ?? "—" },
            { label: "Common hits",    value: debug.common_hit_ids.length },
          ].map(({ label, value }) => (
            <div key={label} className="flex flex-col gap-0.5">
              <span className="text-xs text-tx-muted">{label}</span>
              <span className="text-lg font-mono font-semibold text-tx-primary">{value}</span>
            </div>
          ))}
        </div>
      </Card>

      {/* Diff table */}
      <DiffTable
        alignments={debug.alignments}
        backendA={result.backend_a}
        backendB={result.backend_b}
      />

      {/* Side-by-side hits */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {[result.backend_a, result.backend_b].map((bName) => {
          const r = resultByBackend[bName];
          if (!r) return null;
          return (
            <Card key={bName}>
              <div className="flex items-center justify-between mb-3">
                <span className="text-sm font-semibold text-tx-primary">{bName}</span>
                <Badge variant="info">{r.latency_ms.toFixed(1)}ms</Badge>
              </div>
              <div className="flex flex-col gap-2">
                {r.hits.map((hit, i) => (
                  <HitCard
                    key={hit.id}
                    hit={hit}
                    rank={i + 1}
                    highlight={highlight(bName, hit.id)}
                  />
                ))}
              </div>
              <NativeQuery native={r.native_query} />
            </Card>
          );
        })}
      </div>
    </div>
  );
}

// ── Diagnose mode results ─────────────────────────────────────────────────────

function DiagnoseResults({ result }: { result: DiagnosisResult }) {
  return (
    <div className="flex flex-col gap-4">
      {/* Verdict banner */}
      {result.verdict && (
        <div className="flex gap-3 items-start px-4 py-3 rounded-lg border border-sev-warning/30 bg-sev-warning/5">
          <AlertTriangle size={14} className="text-sev-warning shrink-0 mt-0.5" />
          <div>
            <span className="text-xs font-semibold text-sev-warning uppercase tracking-wide">Verdict</span>
            <p className="text-sm text-tx-primary mt-0.5">{result.verdict}</p>
          </div>
        </div>
      )}

      {/* Summary */}
      <Card>
        <div className="flex items-center justify-between mb-2">
          <span className="text-sm font-semibold text-tx-primary">Summary</span>
          <Badge variant="info">{result.backend_name}</Badge>
        </div>
        <p className="text-sm text-tx-secondary">{result.summary}</p>
        {result.errors.length > 0 && (
          <ul className="mt-2 flex flex-col gap-1">
            {result.errors.map((e, i) => (
              <li key={i} className="text-xs text-sev-error">{e}</li>
            ))}
          </ul>
        )}
      </Card>

      {/* Per-document diagnoses */}
      <div className="flex flex-col gap-3">
        {result.document_diagnoses.map((doc) => (
          <Card key={doc.id}>
            <div className="flex items-center gap-3 flex-wrap mb-2">
              <code className="text-xs font-mono text-tx-code">{doc.id}</code>
              <Badge variant={doc.found ? (doc.retrieved ? "healthy" : "warning") : "error"}>
                {doc.retrieved ? `rank #${doc.rank}` : doc.found ? "found, not retrieved" : "not found"}
              </Badge>
              {doc.score != null && (
                <span className="text-xs font-mono text-tx-secondary">
                  score {doc.score.toFixed(4)}
                </span>
              )}
              {doc.score_gap_to_top != null && (
                <span className="text-xs font-mono text-tx-muted">
                  gap {doc.score_gap_to_top.toFixed(4)}
                </span>
              )}
            </div>
            {doc.findings.length > 0 && (
              <div className="flex flex-col gap-2">
                {doc.findings.map((f, i) => (
                  <FindingCard key={`${f.code}-${i}`} finding={f} />
                ))}
              </div>
            )}
          </Card>
        ))}
      </div>

      {/* Native query */}
      <NativeQuery native={result.native_query} />
    </div>
  );
}

// ── Main panel ────────────────────────────────────────────────────────────────

export function QueryDebugger() {
  const { backends, collectionName } = useVaraStore();

  // Form state
  const [vectorText,       setVectorText]       = useState("");
  const [topK,             setTopK]             = useState("10");
  const [filtersText,      setFiltersText]       = useState("");
  const [selectedBackends, setSelectedBackends] = useState<string[]>([]);
  const [mode,             setMode]             = useState<Mode>("debug");
  const [expectedIds,      setExpectedIds]       = useState("");

  // Result state
  const [result,  setResult]  = useState<AnyResult>(null);
  const [loading, setLoading] = useState(false);
  const [error,   setError]   = useState<string | null>(null);

  const canCompare = selectedBackends.length === 2;

  function toggleBackend(name: string) {
    setSelectedBackends((prev) =>
      prev.includes(name) ? prev.filter((b) => b !== name) : [...prev, name],
    );
  }

  const run = useCallback(async () => {
    // Validate vector
    let vector: number[];
    try {
      const parsed = JSON.parse(vectorText);
      if (!Array.isArray(parsed) || parsed.some((x) => typeof x !== "number")) {
        throw new Error("Must be a JSON array of numbers");
      }
      vector = parsed as number[];
    } catch {
      setError("Invalid vector — paste a JSON array like [0.1, 0.2, ...]");
      return;
    }

    // Parse filters
    let filters: Record<string, unknown> | null = null;
    if (filtersText.trim()) {
      try {
        filters = JSON.parse(filtersText) as Record<string, unknown>;
      } catch {
        setError("Invalid filters JSON");
        return;
      }
    }

    const collection = collectionName;
    if (!collection) { setError("Select a collection first"); return; }
    if (selectedBackends.length === 0) { setError("Select at least one backend"); return; }

    setLoading(true);
    setError(null);
    setResult(null);

    try {
      if (mode === "debug") {
        const r = await debugQuery({
          vector,
          collection,
          backend_names: selectedBackends,
          top_k: Number(topK),
          filters,
        });
        setResult(r);
      } else if (mode === "compare") {
        const r = await compareQuery({
          vector,
          collection,
          backend_a: selectedBackends[0],
          backend_b: selectedBackends[1],
          top_k: Number(topK),
          filters,
        });
        setResult(r);
      } else {
        const ids = expectedIds.split(",").map((s) => s.trim()).filter(Boolean);
        if (ids.length === 0) { setError("Enter at least one expected ID"); setLoading(false); return; }
        const r = await diagnoseQuery({
          vector,
          collection,
          backend_name: selectedBackends[0],
          expected_ids: ids,
          filters,
        });
        setResult(r);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Request failed");
    } finally {
      setLoading(false);
    }
  }, [vectorText, topK, filtersText, selectedBackends, mode, expectedIds, collectionName]);

  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-xl font-semibold text-tx-primary">Query Debugger</h1>

      {/* ── Input card ── */}
      <Card>
        <div className="flex flex-col gap-4">
          {/* Vector textarea */}
          <Textarea
            label="Vector (JSON array)"
            placeholder="[0.123, -0.456, 0.789, ...]"
            rows={3}
            value={vectorText}
            onChange={(e) => setVectorText(e.target.value)}
          />

          {/* top_k + filters row */}
          <div className="flex gap-3 flex-wrap">
            <div className="w-24 shrink-0">
              <Input
                label="top_k"
                type="number"
                min={1}
                max={1000}
                value={topK}
                onChange={(e) => setTopK(e.target.value)}
              />
            </div>
            <div className="flex-1 min-w-[160px]">
              <Input
                label="Filters (JSON, optional)"
                placeholder='{"field": "value"}'
                value={filtersText}
                onChange={(e) => setFiltersText(e.target.value)}
              />
            </div>
          </div>

          {/* Backend checkboxes */}
          {backends.length > 0 && (
            <div className="flex flex-col gap-1">
              <span className="text-xs text-tx-secondary">Backends</span>
              <div className="flex gap-3 flex-wrap">
                {backends.map((b) => (
                  <label
                    key={b.name}
                    className="flex items-center gap-2 cursor-pointer select-none"
                  >
                    <input
                      type="checkbox"
                      checked={selectedBackends.includes(b.name)}
                      onChange={() => toggleBackend(b.name)}
                      className="accent-accent w-4 h-4"
                    />
                    <span className="text-sm text-tx-primary">{b.name}</span>
                    <span className="text-xs text-tx-muted">{b.type}</span>
                  </label>
                ))}
              </div>
            </div>
          )}

          {/* Diagnose — expected IDs */}
          {mode === "diagnose" && (
            <Input
              label="Expected IDs (comma-separated)"
              placeholder="id-001, id-002, id-003"
              value={expectedIds}
              onChange={(e) => setExpectedIds(e.target.value)}
            />
          )}

          {/* Error + Run */}
          {error && <p className="text-xs text-sev-error">{error}</p>}
          <div className="flex items-center justify-between gap-3 flex-wrap">
            <ModeTabs
              mode={mode}
              onChange={(m) => { setMode(m); setResult(null); setError(null); }}
              canCompare={canCompare}
            />
            <Button onClick={run} disabled={loading}>
              {loading ? <Spinner size="sm" /> : <Play size={14} />}
              {loading ? "Running…" : "Run Query"}
            </Button>
          </div>
        </div>
      </Card>

      {/* ── Results ── */}
      {loading && (
        <div className="flex justify-center py-12">
          <Spinner size="lg" />
        </div>
      )}

      {!loading && !result && !error && (
        <EmptyState
          message="No results yet"
          sub="Paste a vector, select backends, and run a query."
        />
      )}

      {!loading && result && mode === "debug" && (
        <DebugResults result={result as DebugQueryResult} />
      )}
      {!loading && result && mode === "compare" && (
        <CompareResults result={result as BackendComparison} />
      )}
      {!loading && result && mode === "diagnose" && (
        <DiagnoseResults result={result as DiagnosisResult} />
      )}
    </div>
  );
}
