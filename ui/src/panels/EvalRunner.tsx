import { useState, useRef, useCallback } from "react";
import { Play, Square, Download } from "lucide-react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import type { EvalProgress } from "../api/types";
import { startEval, connectEvalWS } from "../api/client";
import { useVaraStore } from "../store";
import { Card } from "../components/ui/Card";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Input, Select } from "../components/ui/Input";
import { Spinner } from "../components/ui/Spinner";

// ── Types ─────────────────────────────────────────────────────────────────────

type Status = "idle" | "running" | "complete" | "error";
type Source = "csv" | "json" | "collection";

interface ChartPoint {
  query: number;
  ndcg?: number;
  mrr?: number;
  recall?: number;
}

// ── Progress bar ──────────────────────────────────────────────────────────────

function ProgressBar({ value, max }: { value: number; max: number }) {
  const pct = max > 0 ? Math.min(100, (value / max) * 100) : 0;
  return (
    <div className="flex items-center gap-3">
      <div className="flex-1 h-2 bg-bg-border rounded-full overflow-hidden">
        <div
          className="h-full bg-accent rounded-full transition-all duration-300"
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="text-xs font-mono text-tx-secondary w-20 text-right shrink-0">
        {value} / {max} queries
      </span>
    </div>
  );
}

// ── Metric tiles ──────────────────────────────────────────────────────────────

function MetricTile({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col gap-0.5 bg-bg-raised rounded-lg px-4 py-3">
      <span className="text-xs text-tx-muted">{label}</span>
      <span className="text-xl font-mono font-semibold text-tx-primary">{value}</span>
    </div>
  );
}

// ── Export helper ─────────────────────────────────────────────────────────────

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

export function EvalRunner() {
  const { backends, collections } = useVaraStore();

  // Config
  const [source,         setSource]         = useState<Source>("csv");
  const [sourcePath,     setSourcePath]     = useState("");
  const [nSamples,       setNSamples]       = useState("50");
  const [backendName,    setBackendName]    = useState(backends[0]?.name ?? "");
  const [collectionName, setCollectionName] = useState(
    () => collections.find((c) => c.backend_name === (backends[0]?.name ?? ""))?.name ?? ""
  );
  const [k, setK] = useState("10");

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

  // Build chart data from accumulated events
  const chartData: ChartPoint[] = progress.map((p, i) => ({
    query: i + 1,
    ndcg:   p.metrics["ndcg"] ?? p.metrics["ndcg@k"],
    mrr:    p.metrics["mrr"]  ?? p.metrics["mrr@k"],
    recall: p.metrics["recall"] ?? p.metrics["recall@k"],
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
        ()  => { setStatus("complete"); closeWS.current = null; },
        (msg) => { setErrorMsg(msg); setStatus("error"); closeWS.current = null; },
      );
      closeWS.current = close;
    } catch (e) {
      setErrorMsg(e instanceof Error ? e.message : "Failed to start eval");
      setStatus("error");
    }
  }, [source, sourcePath, nSamples, collectionName, backendName, k]);

  const backendOptions = backends.map((b) => ({ value: b.name, label: b.name }));

  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-xl font-semibold text-tx-primary">Eval Runner</h1>

      {/* ── Config card ── */}
      <Card>
        <div className="flex flex-col gap-4">
          {/* Source tabs */}
          <div className="flex flex-col gap-2">
            <span className="text-xs text-tx-secondary">Dataset source</span>
            <div className="flex gap-1 p-1 bg-bg-raised rounded-lg w-fit">
              {(["csv", "json", "collection"] as const).map((s) => (
                <button
                  key={s}
                  disabled={status === "running"}
                  onClick={() => setSource(s)}
                  className={`px-4 py-1.5 rounded-md text-sm font-medium transition-colors ${
                    source === s
                      ? "bg-accent text-white"
                      : "text-tx-secondary hover:text-tx-primary hover:bg-bg-border disabled:opacity-40"
                  }`}
                >
                  {s === "csv" ? "CSV" : s === "json" ? "JSON" : "Collection"}
                </button>
              ))}
            </div>
          </div>

          {/* Source-specific inputs */}
          {source === "csv" && (
            <Input
              label="File path"
              placeholder="/path/to/eval_dataset.csv"
              value={sourcePath}
              onChange={(e) => setSourcePath(e.target.value)}
              disabled={status === "running"}
            />
          )}
          {source === "json" && (
            <Input
              label="File path"
              placeholder="/path/to/eval_dataset.json"
              value={sourcePath}
              onChange={(e) => setSourcePath(e.target.value)}
              disabled={status === "running"}
            />
          )}
          {source === "collection" && (
            <div className="flex items-start gap-3 flex-wrap">
              <div className="w-32 shrink-0">
                <Input
                  label="n_samples"
                  type="number"
                  min={1}
                  max={10000}
                  value={nSamples}
                  onChange={(e) => setNSamples(e.target.value)}
                  disabled={status === "running"}
                />
              </div>
              <p className="text-xs text-tx-muted self-end pb-2 max-w-xs">
                Samples random vectors from the selected collection and evaluates
                self-retrieval — each vector's only relevant result is itself.
              </p>
            </div>
          )}

          <div className="flex gap-3 flex-wrap">
            <div className="flex-1 min-w-[140px]">
              <Select
                label="Backend"
                options={backendOptions.length ? backendOptions : [{ value: "", label: "No backends" }]}
                value={backendName}
                onChange={(e) => handleBackendChange(e.target.value)}
                disabled={status === "running"}
              />
            </div>
            <div className="flex-1 min-w-[140px]">
              <Select
                label="Collection"
                options={collectionOptions.length ? collectionOptions : [{ value: "", label: "No collections" }]}
                value={collectionName}
                onChange={(e) => setCollectionName(e.target.value)}
                disabled={status === "running"}
              />
            </div>
            <div className="w-24 shrink-0">
              <Input
                label="k"
                type="number"
                min={1}
                max={1000}
                value={k}
                onChange={(e) => setK(e.target.value)}
                disabled={status === "running"}
              />
            </div>
          </div>

          {errorMsg && <p className="text-xs text-sev-error">{errorMsg}</p>}

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
            {jobId && (
              <span className="text-xs font-mono text-tx-muted">job: {jobId}</span>
            )}
            {status === "running" && <Spinner size="sm" />}
            {status === "complete" && <Badge variant="healthy">complete</Badge>}
            {status === "error"    && <Badge variant="error">error</Badge>}
          </div>
        </div>
      </Card>

      {/* ── Live progress ── */}
      {(status === "running" || status === "complete") && progress.length > 0 && (
        <Card>
          <h2 className="text-sm font-semibold text-tx-primary mb-4">
            {status === "running" ? "Live Progress" : "Final Results"}
          </h2>

          {/* Metric tiles */}
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 mb-4">
            {latest && (
              <>
                <MetricTile label="nDCG@k"   value={(latest.metrics["ndcg"]   ?? latest.metrics["ndcg@k"]   ?? 0).toFixed(3)} />
                <MetricTile label="MRR@k"    value={(latest.metrics["mrr"]    ?? latest.metrics["mrr@k"]    ?? 0).toFixed(3)} />
                <MetricTile label="Recall@k" value={(latest.metrics["recall"] ?? latest.metrics["recall@k"] ?? 0).toFixed(3)} />
                <MetricTile label="p50"      value={`${(latest.latency_ms["p50"] ?? 0).toFixed(0)}ms`} />
                <MetricTile label="p95"      value={`${(latest.latency_ms["p95"] ?? 0).toFixed(0)}ms`} />
                <MetricTile label="p99"      value={`${(latest.latency_ms["p99"] ?? 0).toFixed(0)}ms`} />
              </>
            )}
          </div>

          {/* Progress bar */}
          <div className="mb-4">
            <ProgressBar value={latest?.completed ?? 0} max={total || (latest?.total ?? 0)} />
          </div>

          {/* Line chart */}
          {chartData.length > 1 && (
            <ResponsiveContainer width="100%" height={220}>
              <LineChart data={chartData} margin={{ top: 4, right: 16, left: -16, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#2D3148" />
                <XAxis
                  dataKey="query"
                  tick={{ fill: "#64748B", fontSize: 11 }}
                  label={{ value: "query #", position: "insideBottomRight", offset: -4, fill: "#64748B", fontSize: 11 }}
                />
                <YAxis
                  domain={[0, 1]}
                  tick={{ fill: "#64748B", fontSize: 11 }}
                />
                <Tooltip
                  contentStyle={{ background: "#1A1D2E", border: "1px solid #2D3148", borderRadius: 6, fontSize: 12 }}
                  labelStyle={{ color: "#94A3B8" }}
                  itemStyle={{ color: "#E2E8F0" }}
                />
                <Legend wrapperStyle={{ fontSize: 12, color: "#94A3B8" }} />
                <Line type="monotone" dataKey="ndcg"   stroke="#7C6AF7" dot={false} strokeWidth={2} name="nDCG@k"   />
                <Line type="monotone" dataKey="mrr"    stroke="#34D399" dot={false} strokeWidth={2} name="MRR@k"    />
                <Line type="monotone" dataKey="recall" stroke="#60A5FA" dot={false} strokeWidth={2} name="Recall@k" />
              </LineChart>
            </ResponsiveContainer>
          )}

          {/* Export */}
          {status === "complete" && (
            <div className="mt-4 pt-4 border-t border-bg-border flex justify-end">
              <Button variant="ghost" size="sm" onClick={() => exportJSON(progress)}>
                <Download size={13} />
                Export JSON
              </Button>
            </div>
          )}
        </Card>
      )}
    </div>
  );
}
