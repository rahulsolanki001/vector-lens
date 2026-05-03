import { useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { Play, Telescope, AlertTriangle } from "lucide-react";
import type {
  DebugQueryResult,
  BackendComparison,
  DiagnosisResult,
  HitAlignment,
  BackendQueryResult,
  ExpectedDocumentDiagnosis,
} from "../api/types";
import { debugQuery, compareQuery, diagnoseQuery } from "../api/client";
import { useVaraStore } from "../store";
import { Card } from "../components/ui/Card";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Textarea, Select } from "../components/ui/Input";
import { Spinner } from "../components/ui/Spinner";
import { EmptyState } from "../components/ui/EmptyState";
import { CodeBlock } from "../components/ui/CodeBlock";
import { Kicker } from "../components/ui/Kicker";
import { SegmentedControl } from "../components/ui/SegmentedControl";
import { HitCard } from "../components/data/HitCard";
import { FindingCard } from "../components/data/FindingCard";

// ── Types ─────────────────────────────────────────────────────────────────────

type Mode = "debug" | "compare" | "diagnose";
type ComparePayload = BackendComparison | DebugQueryResult;
type AnyResult = DebugQueryResult | ComparePayload | DiagnosisResult | null;

function isBackendComparison(r: ComparePayload): r is BackendComparison {
  return "backend_a" in r;
}

function getNativeQuery(result: AnyResult): Record<string, unknown> | null {
  if (!result) return null;
  if ("document_diagnoses" in result) return result.native_query;
  if ("backend_a" in result) return result.debug.results[0]?.result.native_query ?? null;
  if ("alignments" in result) return result.results[0]?.result.native_query ?? null;
  return null;
}

// ── Stats strip ───────────────────────────────────────────────────────────────

function StatsStrip({ results }: { results: BackendQueryResult[] }) {
  if (results.length === 0) return null;
  return (
    <div className="flex flex-wrap gap-2 mb-4">
      {results.map((r) => (
        <div
          key={r.backend_name}
          className="flex items-center gap-2.5 px-3 py-1.5 bg-bg-surface border border-bg-border rounded-lg"
        >
          <span className="text-xs font-medium text-tx-primary">{r.backend_name}</span>
          <span className="text-xs font-mono text-cy tabular-nums">{r.result.latency_ms.toFixed(1)}ms</span>
          <span className="text-xs text-tx-muted">{r.result.hits.length} hits</span>
        </div>
      ))}
    </div>
  );
}

// ── N-way diff table ──────────────────────────────────────────────────────────

function DiffTable({
  alignments,
  backends,
}: {
  alignments: HitAlignment[];
  backends: string[];
}) {
  if (alignments.length === 0) return null;
  const isPairwise = backends.length === 2;

  const rows = [...alignments].sort((a, b) => {
    const aMissing = a.missing_from.length > 0;
    const bMissing = b.missing_from.length > 0;
    if (aMissing !== bMissing) return aMissing ? 1 : -1;
    const aMin = Math.min(...backends.map((n) => a.ranks[n] ?? Infinity));
    const bMin = Math.min(...backends.map((n) => b.ranks[n] ?? Infinity));
    return aMin - bMin;
  });

  function rankCellClass(row: HitAlignment, backend: string): string {
    const rank = row.ranks[backend];
    if (rank == null) return "text-tx-muted";
    const presentRanks = backends.map((n) => row.ranks[n]).filter((v): v is number => v != null);
    if (presentRanks.length < 2) return "text-tx-secondary";
    if (rank === Math.min(...presentRanks)) return "text-sev-healthy";
    if (rank === Math.max(...presentRanks)) return "text-sev-warning";
    return "text-tx-secondary";
  }

  return (
    <Card>
      <div className="flex items-center justify-between mb-3">
        <Kicker>Result Diff</Kicker>
        {isPairwise && (
          <span className="text-xs font-mono text-tx-muted">
            {backends[0]} · {backends[1]}
          </span>
        )}
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-xs font-mono border-collapse">
          <thead>
            <tr className="border-b border-bg-border">
              <th className="text-left py-2 pr-4 text-tx-muted font-medium">ID</th>
              {backends.map((b) => (
                <th key={b} className="text-right py-2 px-3 text-tx-muted font-medium">
                  {b}
                </th>
              ))}
              <th className="text-right py-2 px-3 text-tx-muted font-medium">spread</th>
              {isPairwise && (
                <>
                  <th className="text-right py-2 px-3 text-tx-muted font-medium">Δ score</th>
                </>
              )}
              <th className="text-left py-2 pl-3 text-tx-muted font-medium">missing</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => {
              const presentRanks = backends
                .map((n) => row.ranks[n])
                .filter((v): v is number => v != null);
              const spread =
                presentRanks.length >= 2
                  ? Math.max(...presentRanks) - Math.min(...presentRanks)
                  : null;
              const spreadClass =
                spread === null
                  ? "text-tx-muted"
                  : spread === 0
                  ? "text-sev-healthy"
                  : spread <= 2
                  ? "text-sev-warning"
                  : "text-sev-error";

              const scoreA = isPairwise ? (row.scores[backends[0]] ?? null) : null;
              const scoreB = isPairwise ? (row.scores[backends[1]] ?? null) : null;
              const scoreDiff =
                scoreA != null && scoreB != null ? scoreA - scoreB : null;

              return (
                <tr
                  key={row.id}
                  className={`border-b border-bg-border last:border-0 hover:bg-bg-raised transition-colors ${
                    row.missing_from.length > 0 ? "opacity-50" : ""
                  }`}
                >
                  <td className="py-1.5 pr-4 text-tx-code max-w-[160px] truncate">{row.id}</td>
                  {backends.map((b) => (
                    <td key={b} className={`py-1.5 px-3 text-right font-semibold ${rankCellClass(row, b)}`}>
                      {row.ranks[b] ?? "—"}
                    </td>
                  ))}
                  <td className={`py-1.5 px-3 text-right font-semibold ${spreadClass}`}>
                    {spread ?? "—"}
                  </td>
                  {isPairwise && (
                    <td
                      className={`py-1.5 px-3 text-right font-semibold ${
                        scoreDiff === null
                          ? "text-tx-muted"
                          : scoreDiff > 0.0001
                          ? "text-sev-healthy"
                          : scoreDiff < -0.0001
                          ? "text-sev-warning"
                          : "text-tx-muted"
                      }`}
                    >
                      {scoreDiff === null
                        ? "—"
                        : scoreDiff > 0
                        ? `+${scoreDiff.toFixed(4)}`
                        : scoreDiff.toFixed(4)}
                    </td>
                  )}
                  <td className="py-1.5 pl-3">
                    {row.missing_from.length > 0 ? (
                      <span className="text-sev-error">{row.missing_from.join(", ")}</span>
                    ) : (
                      <span className="text-tx-muted">—</span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <div className="mt-3 pt-3 border-t border-bg-border flex gap-5 text-xs text-tx-muted font-mono">
        <span><span className="text-sev-healthy">■</span> best rank for this doc</span>
        <span><span className="text-sev-warning">■</span> worst rank for this doc</span>
      </div>
    </Card>
  );
}

// ── Debug mode ────────────────────────────────────────────────────────────────

function DebugResults({
  result,
  onViewInExplorer,
}: {
  result: DebugQueryResult;
  onViewInExplorer: (ids: string[], backend: string) => void;
}) {
  const commonIds = new Set(result.common_hit_ids);
  const allIds = Array.from(
    new Set(result.results.flatMap((br) => br.result.hits.map((h) => h.id))),
  );
  const firstBackend = result.results[0]?.backend_name ?? "";
  const n = result.results.length;
  const gridClass =
    n === 1 ? "grid-cols-1" : n === 2 ? "grid-cols-2" : n === 3 ? "grid-cols-3" : "grid-cols-2";

  return (
    <div className="flex flex-col gap-4">
      <StatsStrip results={result.results} />

      <div className={`grid ${gridClass} gap-4`}>
        {result.results.map((br) => {
          const uniqueIds = new Set(result.unique_hit_ids_by_backend[br.backend_name] ?? []);
          return (
            <Card key={br.backend_name} className="flex flex-col gap-1 p-3">
              <div className="flex items-center justify-between mb-2 px-1">
                <span className="text-xs font-semibold text-tx-primary">{br.backend_name}</span>
                <Badge variant="default">{br.backend_type}</Badge>
              </div>
              {br.result.hits.map((hit, i) => (
                <HitCard
                  key={hit.id}
                  hit={hit}
                  rank={i + 1}
                  highlight={
                    commonIds.has(hit.id)
                      ? "common"
                      : uniqueIds.has(hit.id)
                      ? "unique"
                      : undefined
                  }
                />
              ))}
              {br.result.hits.length === 0 && (
                <p className="text-xs text-tx-muted py-4 text-center">No hits returned</p>
              )}
            </Card>
          );
        })}
        {result.errors.map((e) => (
          <Card key={e.backend_name}>
            <p className="text-xs font-semibold text-tx-primary mb-1">{e.backend_name}</p>
            <p className="text-xs text-sev-error">{e.error}</p>
          </Card>
        ))}
      </div>

      {allIds.length > 0 && (
        <div className="flex justify-end">
          <Button variant="ghost" size="sm" onClick={() => onViewInExplorer(allIds, firstBackend)}>
            <Telescope size={13} />
            View {allIds.length} results in Explorer
          </Button>
        </div>
      )}
    </div>
  );
}

// ── Compare mode ──────────────────────────────────────────────────────────────

function CompareResults({
  result,
  backends,
}: {
  result: ComparePayload;
  backends: string[];
}) {
  const debug = isBackendComparison(result) ? result.debug : result;
  const commonIds = new Set(debug.common_hit_ids);
  const n = backends.length;
  const gridClass = n <= 2 ? "grid-cols-2" : n === 3 ? "grid-cols-3" : "grid-cols-2";

  return (
    <div className="flex flex-col gap-4">
      {/* Pairwise similarity metrics */}
      {isBackendComparison(result) && (
        <Card>
          <Kicker className="mb-3 block">Similarity Metrics</Kicker>
          <div className="grid grid-cols-4 gap-4">
            {[
              { label: "Jaccard",     value: result.jaccard_similarity.toFixed(4) },
              { label: "Rank ρ",      value: result.rank_spearman?.toFixed(4) ?? "—" },
              { label: "Score ρ",     value: result.score_spearman?.toFixed(4) ?? "—" },
              { label: "Common hits", value: String(debug.common_hit_ids.length) },
            ].map(({ label, value }) => (
              <div key={label} className="flex flex-col gap-0.5">
                <Kicker>{label}</Kicker>
                <span className="text-lg font-mono font-semibold text-tx-primary mt-1">{value}</span>
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* Multi-backend stats strip */}
      {!isBackendComparison(result) && <StatsStrip results={debug.results} />}

      {/* N-way diff table */}
      <DiffTable alignments={debug.alignments} backends={backends} />

      {/* Side-by-side hit lists */}
      <div className={`grid ${gridClass} gap-4`}>
        {backends.map((bName) => {
          const r = debug.results.find((x) => x.backend_name === bName);
          if (!r) return null;
          const uniqueIds = new Set(debug.unique_hit_ids_by_backend[bName] ?? []);
          return (
            <Card key={bName} className="flex flex-col gap-1 p-3">
              <div className="flex items-center justify-between mb-2 px-1">
                <span className="text-xs font-semibold text-tx-primary">{bName}</span>
                <Badge variant="default">{r.backend_type}</Badge>
              </div>
              {r.result.hits.map((hit, i) => (
                <HitCard
                  key={hit.id}
                  hit={hit}
                  rank={i + 1}
                  highlight={
                    commonIds.has(hit.id) ? "common" : uniqueIds.has(hit.id) ? "unique" : undefined
                  }
                />
              ))}
            </Card>
          );
        })}
      </div>
    </div>
  );
}

// ── Diagnose mode ─────────────────────────────────────────────────────────────

function rankBadgeVariant(doc: ExpectedDocumentDiagnosis): "healthy" | "warning" | "error" {
  if (!doc.retrieved) return doc.found ? "warning" : "error";
  if (doc.rank !== null && doc.rank <= 3) return "healthy";
  if (doc.rank !== null && doc.rank <= 8) return "warning";
  return "error";
}

function ConicRing({ ratio }: { ratio: number }) {
  const pct = Math.round(Math.max(0, Math.min(1, ratio)) * 100);
  return (
    <div
      className="w-10 h-10 rounded-full shrink-0"
      style={{
        background: `conic-gradient(#8B7DFF ${pct}%, rgba(255,255,255,0.06) 0%)`,
        WebkitMask: "radial-gradient(transparent 55%, black 56%)",
        mask: "radial-gradient(transparent 55%, black 56%)",
      }}
    />
  );
}

function DiagnoseResults({
  result,
  onViewInExplorer,
}: {
  result: DiagnosisResult;
  onViewInExplorer: (ids: string[], backend: string) => void;
}) {
  const seedIds = Array.from(new Set([...result.retrieved_ids, ...result.expected_ids]));

  return (
    <div className="flex flex-col gap-4">
      {/* Verdict banner */}
      {result.verdict && (
        <div
          className="flex gap-4 items-start px-5 py-4 rounded-xl border border-sev-warning/25"
          style={{
            background:
              "linear-gradient(135deg, rgba(242,180,90,0.08) 0%, rgba(242,180,90,0.03) 100%)",
          }}
        >
          <div className="w-8 h-8 rounded-lg bg-sev-warning/15 flex items-center justify-center shrink-0 mt-0.5">
            <AlertTriangle size={15} className="text-sev-warning" />
          </div>
          <div>
            <Kicker className="text-sev-warning/80">Verdict</Kicker>
            <p className="text-sm font-medium text-tx-primary mt-1">{result.verdict}</p>
          </div>
        </div>
      )}

      {/* Summary */}
      <Card>
        <div className="flex items-center justify-between mb-2">
          <Kicker>Summary</Kicker>
          <div className="flex items-center gap-2">
            <Badge variant="info">{result.backend_name}</Badge>
            {seedIds.length > 0 && (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => onViewInExplorer(seedIds, result.backend_name)}
              >
                <Telescope size={12} />
                View in Explorer
              </Button>
            )}
          </div>
        </div>
        <p className="text-sm text-tx-secondary">{result.summary}</p>
        {result.errors.length > 0 && (
          <ul className="mt-2 flex flex-col gap-1">
            {result.errors.map((e, i) => (
              <li key={i} className="text-xs text-sev-error">
                {e}
              </li>
            ))}
          </ul>
        )}
      </Card>

      {/* Ground truth tiles */}
      {result.total_expected > 0 && (
        <div className="grid grid-cols-3 gap-3">
          {[
            {
              label: `Recall@${result.top_k}`,
              ratio: result.recall_at_k ?? 0,
              display: result.recall_at_k != null ? result.recall_at_k.toFixed(3) : "—",
            },
            {
              label: "MRR",
              ratio: result.mrr ?? 0,
              display: result.mrr != null ? result.mrr.toFixed(3) : "—",
            },
            {
              label: "Hits",
              ratio: result.hit_count / result.total_expected,
              display: `${result.hit_count} / ${result.total_expected}`,
            },
          ].map(({ label, ratio, display }) => (
            <div
              key={label}
              className="flex items-center justify-between bg-bg-raised rounded-xl px-4 py-3"
            >
              <div className="flex flex-col gap-0.5">
                <Kicker>{label}</Kicker>
                <span className="text-xl font-mono font-semibold text-tx-primary mt-0.5">
                  {display}
                </span>
              </div>
              <ConicRing ratio={ratio} />
            </div>
          ))}
        </div>
      )}

      {/* Per-document diagnoses */}
      <div className="flex flex-col gap-3">
        {result.document_diagnoses.map((doc) => (
          <Card key={doc.id}>
            <div className="flex items-center gap-3 flex-wrap mb-2">
              <code className="text-xs font-mono text-tx-code">{doc.id}</code>
              <Badge variant={rankBadgeVariant(doc)}>
                {doc.retrieved
                  ? `rank #${doc.rank}`
                  : doc.found
                  ? "found, not retrieved"
                  : "not found"}
              </Badge>
              {doc.score != null && (
                <span className="text-xs font-mono text-tx-secondary tabular-nums">
                  score {doc.score.toFixed(4)}
                </span>
              )}
              {doc.score_gap_to_top != null && (
                <span className="text-xs font-mono text-tx-muted tabular-nums">
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
    </div>
  );
}

// ── Main panel ────────────────────────────────────────────────────────────────

const MODE_OPTIONS: { value: Mode; label: string }[] = [
  { value: "debug", label: "Debug" },
  { value: "compare", label: "Compare" },
  { value: "diagnose", label: "Diagnose" },
];

export function QueryDebugger() {
  const { backends, collections, setExplorerSeed } = useVaraStore();
  const navigate = useNavigate();

  const handleViewInExplorer = useCallback(
    (ids: string[], backend: string) => {
      setExplorerSeed(ids, backend);
      navigate("/explore");
    },
    [setExplorerSeed, navigate],
  );

  // Form state
  const [vectorText, setVectorText] = useState("");
  const [topK, setTopK] = useState(10);
  const [filtersText, setFiltersText] = useState("");
  const [selectedBackends, setSelectedBackends] = useState<string[]>([]);
  const [collectionName, setCollectionName] = useState(() => collections[0]?.name ?? "");
  const [mode, setMode] = useState<Mode>("debug");
  const [expectedIds, setExpectedIds] = useState("");

  // Result state
  const [result, setResult] = useState<AnyResult>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const canCompare = selectedBackends.length >= 2;

  const collectionOptions = (
    selectedBackends.length > 0
      ? collections.filter((c) => selectedBackends.includes(c.backend_name))
      : collections
  ).filter((c, i, arr) => arr.findIndex((x) => x.name === c.name) === i);

  function toggleBackend(name: string) {
    setSelectedBackends((prev) =>
      prev.includes(name) ? prev.filter((b) => b !== name) : [...prev, name],
    );
  }

  const run = useCallback(async () => {
    let vector: number[];
    try {
      const parsed = JSON.parse(vectorText);
      if (!Array.isArray(parsed) || parsed.some((x) => typeof x !== "number"))
        throw new Error();
      vector = parsed as number[];
    } catch {
      setError("Invalid vector — paste a JSON array like [0.1, 0.2, ...]");
      return;
    }

    let filters: Record<string, unknown> | null = null;
    if (filtersText.trim()) {
      try {
        filters = JSON.parse(filtersText) as Record<string, unknown>;
      } catch {
        setError("Invalid filters JSON");
        return;
      }
    }

    if (!collectionName) { setError("Select a collection first"); return; }
    if (selectedBackends.length === 0) { setError("Select at least one backend"); return; }

    setLoading(true);
    setError(null);
    setResult(null);

    try {
      if (mode === "debug") {
        setResult(
          await debugQuery({
            vector,
            collection: collectionName,
            backend_names: selectedBackends,
            top_k: topK,
            filters,
          }),
        );
      } else if (mode === "compare") {
        if (selectedBackends.length === 2) {
          setResult(
            await compareQuery({
              vector,
              collection: collectionName,
              backend_a: selectedBackends[0],
              backend_b: selectedBackends[1],
              top_k: topK,
              filters,
            }),
          );
        } else {
          setResult(
            await debugQuery({
              vector,
              collection: collectionName,
              backend_names: selectedBackends,
              top_k: topK,
              filters,
            }),
          );
        }
      } else {
        const ids = expectedIds.split(",").map((s) => s.trim()).filter(Boolean);
        if (ids.length === 0) {
          setError("Enter at least one expected ID");
          setLoading(false);
          return;
        }
        setResult(
          await diagnoseQuery({
            vector,
            collection: collectionName,
            backend_name: selectedBackends[0],
            expected_ids: ids,
            filters,
          }),
        );
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Request failed");
    } finally {
      setLoading(false);
    }
  }, [vectorText, topK, filtersText, selectedBackends, mode, expectedIds, collectionName]);

  const nativeQuery = getNativeQuery(result);

  return (
    <div className="-mx-6 -mt-6 flex items-start min-h-[calc(100vh-64px)]">
      {/* ── Input column ── */}
      <div className="w-[380px] shrink-0 sticky top-0 self-start max-h-[calc(100vh-64px)] overflow-y-auto border-r border-bg-border flex flex-col gap-5 px-6 py-6">
        <div className="flex items-center justify-between">
          <h1 className="text-base font-semibold text-tx-primary">Query Debugger</h1>
          <SegmentedControl
            options={MODE_OPTIONS.map((o) => ({
              ...o,
              label: o.value === "compare" && !canCompare ? o.label : o.label,
            }))}
            value={mode}
            onChange={(m) => { setMode(m); setResult(null); setError(null); }}
          />
        </div>

        {/* Vector */}
        <div className="flex flex-col gap-1.5">
          <Kicker>Vector</Kicker>
          <Textarea
            placeholder="[0.123, -0.456, 0.789, ...]"
            rows={3}
            value={vectorText}
            onChange={(e) => setVectorText(e.target.value)}
          />
        </div>

        {/* Backends */}
        {backends.length > 0 && (
          <div className="flex flex-col gap-2">
            <Kicker>Backends</Kicker>
            <div className="flex flex-wrap gap-2">
              {backends.map((b) => {
                const active = selectedBackends.includes(b.name);
                return (
                  <button
                    key={b.name}
                    onClick={() => toggleBackend(b.name)}
                    className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-lg border text-xs font-medium transition-all ${
                      active
                        ? "bg-accent/10 border-accent/40 text-accent"
                        : "bg-bg-raised border-bg-border text-tx-secondary hover:text-tx-primary"
                    }`}
                  >
                    {b.name}
                    <span
                      className={`px-1.5 py-0.5 rounded font-mono text-[10px] ${
                        active ? "bg-accent/20 text-accent/70" : "bg-bg-border text-tx-muted"
                      }`}
                    >
                      {b.type}
                    </span>
                  </button>
                );
              })}
            </div>
            {mode === "compare" && !canCompare && (
              <p className="text-xs text-tx-muted">Select 2 or more backends to compare</p>
            )}
          </div>
        )}

        {/* Collection */}
        <div className="flex flex-col gap-1.5">
          <Kicker>Collection</Kicker>
          <Select
            value={collectionName}
            onChange={(e) => setCollectionName(e.target.value)}
            options={
              collectionOptions.length
                ? collectionOptions.map((c) => ({ value: c.name, label: c.name }))
                : [{ value: "", label: "No collections" }]
            }
          />
        </div>

        {/* Top-K slider */}
        <div className="flex flex-col gap-2">
          <div className="flex items-center justify-between">
            <Kicker>Top-K</Kicker>
            <span className="font-mono text-sm font-semibold text-tx-primary tabular-nums w-8 text-right">
              {topK}
            </span>
          </div>
          <input
            type="range"
            min={1}
            max={100}
            value={topK}
            onChange={(e) => setTopK(Number(e.target.value))}
            className="w-full"
          />
        </div>

        {/* Filters */}
        <div className="flex flex-col gap-1.5">
          <Kicker>Filters (JSON, optional)</Kicker>
          <Textarea
            placeholder='{"field": "value"}'
            rows={2}
            value={filtersText}
            onChange={(e) => setFiltersText(e.target.value)}
          />
        </div>

        {/* Diagnose — expected IDs */}
        {mode === "diagnose" && (
          <div className="flex flex-col gap-1.5">
            <Kicker>Expected IDs (comma-separated)</Kicker>
            <Textarea
              placeholder="id-001, id-002, id-003"
              rows={2}
              value={expectedIds}
              onChange={(e) => setExpectedIds(e.target.value)}
            />
          </div>
        )}

        {/* Error */}
        {error && <p className="text-xs text-sev-error">{error}</p>}

        {/* Run */}
        <Button onClick={run} disabled={loading} hint="↵" className="w-full">
          {loading ? <Spinner size="sm" /> : <Play size={13} />}
          {loading ? "Running…" : "Run"}
        </Button>

        {/* Native query preview — bottom of input column */}
        {nativeQuery && (
          <div className="flex flex-col gap-1.5 mt-auto pt-4 border-t border-bg-border">
            <Kicker>Native Query</Kicker>
            <CodeBlock code={JSON.stringify(nativeQuery, null, 2)} maxHeight="200px" />
          </div>
        )}
      </div>

      {/* ── Results column ── */}
      <div className="flex-1 min-w-0 px-6 py-6">
        {loading && (
          <div className="flex justify-center py-20">
            <Spinner size="lg" />
          </div>
        )}

        {!loading && !result && !error && (
          <EmptyState
            message="Awaiting query"
            sub="Configure your vector and backends, then run to inspect retrieval."
          />
        )}

        {!loading && result && mode === "debug" && (
          <DebugResults
            result={result as DebugQueryResult}
            onViewInExplorer={handleViewInExplorer}
          />
        )}

        {!loading && result && mode === "compare" && (
          <CompareResults
            result={result as ComparePayload}
            backends={selectedBackends}
          />
        )}

        {!loading && result && mode === "diagnose" && (
          <DiagnoseResults
            result={result as DiagnosisResult}
            onViewInExplorer={handleViewInExplorer}
          />
        )}
      </div>
    </div>
  );
}
