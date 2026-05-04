import { useState, useRef, useCallback } from "react";
import { Play, Square, Download, Activity } from "lucide-react";
import type { EvalProgress } from "../api/types";
import { startEval, connectEvalWS } from "../api/client";
import { useVaraStore } from "../store";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Input, Select } from "../components/ui/Input";
import { Spinner } from "../components/ui/Spinner";
import { Kicker } from "../components/ui/Kicker";
import { SegmentedControl } from "../components/ui/SegmentedControl";
import { EmptyState } from "../components/ui/EmptyState";

// ── Types ─────────────────────────────────────────────────────────────────────

type Status = "idle" | "running" | "complete" | "error";
type Source = "csv" | "json" | "collection";

interface ChartPoint {
  ndcg: number;
  mrr: number;
}

// ── SVG Sparkline ─────────────────────────────────────────────────────────────

function Sparkline({ data, height = 140 }: { data: ChartPoint[]; height?: number }) {
  if (data.length < 2) return null;

  const VW = 600;
  const VH = height;
  const pad = { top: 8, right: 12, bottom: 24, left: 30 };
  const iW = VW - pad.left - pad.right;
  const iH = VH - pad.top - pad.bottom;

  const toX = (i: number) => pad.left + (i / (data.length - 1)) * iW;
  const toY = (v: number) => pad.top + (1 - Math.max(0, Math.min(1, v))) * iH;

  function makePath(key: keyof ChartPoint) {
    return data
      .map((p, i) => `${i === 0 ? "M" : "L"}${toX(i).toFixed(1)} ${toY(p[key]).toFixed(1)}`)
      .join(" ");
  }

  const gridVals = [0, 0.25, 0.5, 0.75, 1];

  return (
    <svg
      viewBox={`0 0 ${VW} ${VH}`}
      width="100%"
      height={height}
      className="overflow-visible"
      style={{ fontFamily: "Geist Mono, monospace" }}
    >
      {/* Grid */}
      {gridVals.map((v) => (
        <line
          key={v}
          x1={pad.left}
          x2={VW - pad.right}
          y1={toY(v)}
          y2={toY(v)}
          stroke="#1F2330"
          strokeWidth={1}
        />
      ))}
      {/* Y labels */}
      {[0, 0.5, 1].map((v) => (
        <text key={v} x={pad.left - 5} y={toY(v) + 4} fill="#6E7689" fontSize={10} textAnchor="end">
          {v.toFixed(1)}
        </text>
      ))}
      {/* nDCG — violet solid */}
      <path
        d={makePath("ndcg")}
        fill="none"
        stroke="#8B7DFF"
        strokeWidth={2}
        strokeLinejoin="round"
        strokeLinecap="round"
      />
      {/* MRR — cyan dashed */}
      <path
        d={makePath("mrr")}
        fill="none"
        stroke="#5DE3FF"
        strokeWidth={2}
        strokeLinejoin="round"
        strokeLinecap="round"
        strokeDasharray="5 3"
      />
      {/* X axis label */}
      <text x={VW / 2} y={VH - 4} fill="#6E7689" fontSize={10} textAnchor="middle">
        query #
      </text>
    </svg>
  );
}

// ── Sparkline legend ──────────────────────────────────────────────────────────

function SparklineLegend() {
  return (
    <div className="flex items-center gap-4">
      <div className="flex items-center gap-1.5">
        <div className="w-5 h-0.5 rounded-full bg-accent" />
        <span className="text-[11px] font-mono text-tx-muted">nDCG@k</span>
      </div>
      <div className="flex items-center gap-1.5">
        <svg width="20" height="2" viewBox="0 0 20 2">
          <line x1="0" y1="1" x2="20" y2="1" stroke="#5DE3FF" strokeWidth="2" strokeDasharray="5 3" />
        </svg>
        <span className="text-[11px] font-mono text-tx-muted">MRR@k</span>
      </div>
    </div>
  );
}

// ── Latency bars ──────────────────────────────────────────────────────────────

function LatencyBars({ p50, p95, p99 }: { p50: number; p95: number; p99: number }) {
  const max = Math.max(p99, 1);
  const bars = [
    { label: "p50", value: p50, color: "#5BD6A8" },
    { label: "p95", value: p95, color: "#F2B45A" },
    { label: "p99", value: p99, color: "#F47272" },
  ];
  return (
    <div className="flex items-end gap-2 h-20">
      {bars.map(({ label, value, color }) => {
        const barH = Math.max(4, (value / max) * 56);
        return (
          <div key={label} className="flex flex-col items-center gap-1 flex-1">
            <span className="text-[10px] font-mono" style={{ color }}>
              {value.toFixed(0)}ms
            </span>
            <div
              className="w-full rounded-sm"
              style={{ height: `${barH}px`, background: color, opacity: 0.75 }}
            />
            <span className="text-[10px] font-mono text-tx-muted">{label}</span>
          </div>
        );
      })}
    </div>
  );
}

// ── Metric tile ───────────────────────────────────────────────────────────────

function MetricTile({
  label,
  value,
  color,
}: {
  label: string;
  value: string;
  color?: string;
}) {
  return (
    <div
      className="flex flex-col gap-1.5 bg-bg-raised rounded-lg px-4 py-3"
      style={{ boxShadow: "inset 0 1px 0 rgba(255,255,255,0.04)" }}
    >
      <Kicker>{label}</Kicker>
      <span
        className="text-lg font-mono font-semibold tabular-nums"
        style={{ color: color ?? "#ECEDEF" }}
      >
        {value}
      </span>
    </div>
  );
}

// ── Progress bar ──────────────────────────────────────────────────────────────

function ProgressBar({ value, max }: { value: number; max: number }) {
  const pct = max > 0 ? Math.min(100, (value / max) * 100) : 0;
  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex justify-between items-center">
        <span className="text-[11px] font-mono text-tx-muted">
          {value} / {max || "?"} queries
        </span>
        <span className="text-[11px] font-mono text-tx-secondary">{pct.toFixed(0)}%</span>
      </div>
      <div className="h-1.5 bg-bg-border rounded-full overflow-hidden">
        <div
          className="h-full rounded-full transition-all duration-300"
          style={{ width: `${pct}%`, background: "var(--grad)" }}
        />
      </div>
    </div>
  );
}

// ── Export ────────────────────────────────────────────────────────────────────

function exportJSON(data: EvalProgress[]) {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `vara_eval_${Date.now()}.json`;
  a.click();
  URL.revokeObjectURL(url);
}

// ── Panel ─────────────────────────────────────────────────────────────────────

const SOURCE_OPTIONS: { value: Source; label: string }[] = [
  { value: "csv",        label: "CSV" },
  { value: "json",       label: "JSON" },
  { value: "collection", label: "Collection" },
];

export function EvalRunner() {
  const { backends, collections } = useVaraStore();

  // Config
  const [source,         setSource]         = useState<Source>("csv");
  const [sourcePath,     setSourcePath]     = useState("");
  const [nSamples,       setNSamples]       = useState("50");
  const [backendName,    setBackendName]    = useState(backends[0]?.name ?? "");
  const [collectionName, setCollectionName] = useState(
    () => collections.find((c) => c.backend_name === (backends[0]?.name ?? ""))?.name ?? "",
  );
  const [k, setK] = useState("10");

  const backendOptions = backends.map((b) => ({ value: b.name, label: b.name }));
  const collectionOptions = collections
    .filter((c) => c.backend_name === backendName)
    .map((c) => ({ value: c.name, label: c.name }));

  function handleBackendChange(name: string) {
    setBackendName(name);
    setCollectionName(collections.find((c) => c.backend_name === name)?.name ?? "");
  }

  // Run state
  const [status,   setStatus]   = useState<Status>("idle");
  const [jobId,    setJobId]    = useState<string | null>(null);
  const [total,    setTotal]    = useState(0);
  const [progress, setProgress] = useState<EvalProgress[]>([]);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const closeWS = useRef<(() => void) | null>(null);

  const latest = progress[progress.length - 1] ?? null;

  const chartData: ChartPoint[] = progress.map((p) => ({
    ndcg: p.metrics["ndcg"] ?? p.metrics["ndcg@k"] ?? 0,
    mrr:  p.metrics["mrr"]  ?? p.metrics["mrr@k"]  ?? 0,
  }));

  const stop = useCallback(() => {
    closeWS.current?.();
    setStatus("idle");
  }, []);

  const run = useCallback(async () => {
    if (source !== "collection" && !sourcePath.trim()) {
      setErrorMsg("Dataset path is required"); return;
    }
    if (!collectionName) { setErrorMsg("Select a collection first"); return; }
    if (!backendName)    { setErrorMsg("Select a backend"); return; }

    setErrorMsg(null);
    setProgress([]);
    setStatus("running");
    setJobId(null);

    try {
      const resp = await startEval({
        source,
        ...(source !== "collection"
          ? { source_path: sourcePath.trim() }
          : { n_samples: Number(nSamples) }),
        collection: collectionName,
        backend_name: backendName,
        k: Number(k),
      });

      setJobId(resp.job_id);
      setTotal(resp.total_queries);

      const close = connectEvalWS(
        resp.job_id,
        (p) => setProgress((prev) => [...prev, p]),
        ()    => { setStatus("complete"); closeWS.current = null; },
        (msg) => { setErrorMsg(msg); setStatus("error"); closeWS.current = null; },
      );
      closeWS.current = close;
    } catch (e) {
      setErrorMsg(e instanceof Error ? e.message : "Failed to start eval");
      setStatus("error");
    }
  }, [source, sourcePath, nSamples, collectionName, backendName, k]);

  if (backends.length === 0) {
    return (
      <EmptyState
        message="No backends configured"
        sub="Make sure the Vara server is running and /api/config is reachable."
      />
    );
  }

  const hasResults = (status === "running" || status === "complete") && progress.length > 0;

  return (
    <div className="-mx-6 -mt-6 flex items-start min-h-[calc(100vh-64px)]">
      {/* ── Left: config ── */}
      <div className="w-[340px] shrink-0 sticky top-0 self-start max-h-[calc(100vh-64px)] overflow-y-auto border-r border-bg-border flex flex-col gap-5 px-6 py-6">
        {/* Header */}
        <div className="flex items-center justify-between gap-2">
          <h1 className="text-lg font-semibold text-tx-primary">Eval Runner</h1>
          {status === "running"  && <Badge variant="vio">running</Badge>}
          {status === "complete" && <Badge variant="healthy">complete</Badge>}
          {status === "error"    && <Badge variant="error">error</Badge>}
        </div>

        {/* Source */}
        <div className="flex flex-col gap-2">
          <Kicker>Dataset source</Kicker>
          <SegmentedControl
            options={SOURCE_OPTIONS}
            value={source}
            onChange={(v) => setSource(v)}
          />
        </div>

        {/* Source-specific input */}
        {source === "csv" && (
          <Input
            label="File path"
            placeholder="/path/to/dataset.csv"
            value={sourcePath}
            onChange={(e) => setSourcePath(e.target.value)}
            disabled={status === "running"}
          />
        )}
        {source === "json" && (
          <Input
            label="File path"
            placeholder="/path/to/dataset.json"
            value={sourcePath}
            onChange={(e) => setSourcePath(e.target.value)}
            disabled={status === "running"}
          />
        )}
        {source === "collection" && (
          <div className="flex flex-col gap-1.5">
            <Input
              label="n_samples"
              type="number"
              min={1}
              max={10000}
              value={nSamples}
              onChange={(e) => setNSamples(e.target.value)}
              disabled={status === "running"}
            />
            <p className="text-[11px] text-tx-muted leading-relaxed">
              Samples random vectors and evaluates self-retrieval — each vector's only relevant result is itself.
            </p>
          </div>
        )}

        {/* Backend + collection */}
        <div className="flex flex-col gap-3">
          <Select
            label="Backend"
            options={backendOptions.length ? backendOptions : [{ value: "", label: "No backends" }]}
            value={backendName}
            onChange={(e) => handleBackendChange(e.target.value)}
            disabled={status === "running"}
          />
          <Select
            label="Collection"
            options={collectionOptions.length ? collectionOptions : [{ value: "", label: "No collections" }]}
            value={collectionName}
            onChange={(e) => setCollectionName(e.target.value)}
            disabled={status === "running"}
          />
        </div>

        {/* k */}
        <Input
          label="k (top-k)"
          type="number"
          min={1}
          max={1000}
          value={k}
          onChange={(e) => setK(e.target.value)}
          disabled={status === "running"}
        />

        {errorMsg && <p className="text-xs text-sev-error">{errorMsg}</p>}

        {/* Actions */}
        <div className="flex items-center gap-3">
          {status === "running" ? (
            <Button variant="ghost" onClick={stop}>
              <Square size={14} />
              Stop
            </Button>
          ) : (
            <Button onClick={run}>
              <Play size={14} />
              Run Eval
            </Button>
          )}
          {status === "running" && <Spinner size="sm" />}
        </div>

        {jobId && (
          <p className="text-[11px] font-mono text-tx-muted break-all">job {jobId}</p>
        )}
      </div>

      {/* ── Right: live dashboard ── */}
      <div className="flex-1 min-w-0 px-6 py-6 flex flex-col gap-6">
        {!hasResults ? (
          <div className="flex flex-col items-center justify-center h-full min-h-[320px] gap-3">
            <div
              className="w-12 h-12 rounded-xl flex items-center justify-center"
              style={{ background: "var(--vio-soft)" }}
            >
              <Activity size={22} className="text-accent" />
            </div>
            <p className="text-sm text-tx-secondary">Configure and run an eval to see live metrics.</p>
          </div>
        ) : (
          <>
            {/* Stats strip */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              <MetricTile
                label="nDCG@k"
                value={(latest?.metrics["ndcg"] ?? latest?.metrics["ndcg@k"] ?? 0).toFixed(3)}
                color="#8B7DFF"
              />
              <MetricTile
                label="MRR@k"
                value={(latest?.metrics["mrr"] ?? latest?.metrics["mrr@k"] ?? 0).toFixed(3)}
                color="#5DE3FF"
              />
              <MetricTile
                label="Recall@k"
                value={(latest?.metrics["recall"] ?? latest?.metrics["recall@k"] ?? 0).toFixed(3)}
                color="#5BD6A8"
              />
              <MetricTile
                label="p50 latency"
                value={`${(latest?.latency_ms["p50"] ?? 0).toFixed(0)}ms`}
              />
            </div>

            {/* Progress */}
            <ProgressBar
              value={latest?.completed ?? 0}
              max={total || (latest?.total ?? 0)}
            />

            {/* Sparkline */}
            {chartData.length > 1 && (
              <div
                className="bg-bg-surface border border-bg-border rounded-xl p-4"
                style={{ boxShadow: "inset 0 1px 0 rgba(255,255,255,0.04)" }}
              >
                <div className="flex items-center justify-between mb-3">
                  <Kicker>Metrics over time</Kicker>
                  <SparklineLegend />
                </div>
                <Sparkline data={chartData} />
              </div>
            )}

            {/* Latency breakdown */}
            {latest && (
              <div
                className="bg-bg-surface border border-bg-border rounded-xl p-4"
                style={{ boxShadow: "inset 0 1px 0 rgba(255,255,255,0.04)" }}
              >
                <Kicker className="mb-3 block">Latency breakdown</Kicker>
                <LatencyBars
                  p50={latest.latency_ms["p50"] ?? 0}
                  p95={latest.latency_ms["p95"] ?? 0}
                  p99={latest.latency_ms["p99"] ?? 0}
                />
              </div>
            )}

            {/* Export */}
            {status === "complete" && (
              <div className="flex justify-end pt-2">
                <Button variant="ghost" size="sm" onClick={() => exportJSON(progress)}>
                  <Download size={13} />
                  Export JSON
                </Button>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
