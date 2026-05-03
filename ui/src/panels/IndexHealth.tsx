import { useState, useCallback } from "react";
import { RefreshCw, ChevronDown, ChevronRight, HardDrive } from "lucide-react";
import type { HealthReport, HealthStatus } from "../api/types";
import { getHealth } from "../api/client";
import { useVaraStore } from "../store";
import { Card } from "../components/ui/Card";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Spinner } from "../components/ui/Spinner";
import { EmptyState } from "../components/ui/EmptyState";
import { FindingCard } from "../components/data/FindingCard";

// ── Status dot ────────────────────────────────────────────────────────────────

const dotColor: Record<HealthStatus, string> = {
  healthy:   "bg-sev-healthy",
  degraded:  "bg-sev-warning",
  unhealthy: "bg-sev-error",
};

function StatusDot({ status }: { status: HealthStatus }) {
  return (
    <span
      className={`inline-block w-2.5 h-2.5 rounded-full shrink-0 ${dotColor[status]}`}
    />
  );
}

// ── Stats sub-section ─────────────────────────────────────────────────────────

function StatsSection({ report }: { report: HealthReport }) {
  const [open, setOpen] = useState(false);
  const s = report.stats;
  if (!s) return null;

  const rows: { label: string; value: string | number | null }[] = [
    { label: "Vectors",    value: s.vector_count?.toLocaleString() ?? "—" },
    { label: "Dimension",  value: s.dimension ?? "—" },
    { label: "Distance",   value: s.distance_metric ?? "—" },
    { label: "Index type", value: s.index_type ?? "—" },
    {
      label: "Disk",
      value: s.disk_bytes != null
        ? `${(s.disk_bytes / 1024 / 1024).toFixed(1)} MB`
        : "—",
    },
    {
      label: "RAM",
      value: s.ram_bytes != null
        ? `${(s.ram_bytes / 1024 / 1024).toFixed(1)} MB`
        : "—",
    },
  ];

  return (
    <div className="mt-3 pt-3 border-t border-bg-border">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-1 text-xs text-tx-muted hover:text-tx-secondary transition-colors"
      >
        {open ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
        <HardDrive size={12} />
        <span>Stats</span>
      </button>
      {open && (
        <div className="mt-2 grid grid-cols-2 sm:grid-cols-3 gap-x-6 gap-y-1">
          {rows.map(({ label, value }) => (
            <div key={label} className="flex items-baseline gap-1">
              <span className="text-xs text-tx-muted w-20 shrink-0">{label}</span>
              <span className="text-xs font-mono text-tx-secondary">{String(value)}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Per-backend card ──────────────────────────────────────────────────────────

interface BackendCardProps {
  backend: string;
  collection: string;
  report: HealthReport | null;
  loading: boolean;
  onCheck: () => void;
}

function BackendCard({ backend, collection, report, loading, onCheck }: BackendCardProps) {
  return (
    <Card className="flex flex-col gap-3">
      {/* Header row */}
      <div className="flex items-center gap-3 flex-wrap">
        {report ? (
          <StatusDot status={report.status} />
        ) : (
          <span className="inline-block w-2.5 h-2.5 rounded-full bg-bg-border shrink-0" />
        )}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-sm font-semibold text-tx-primary">{backend}</span>
            <span className="text-xs font-mono text-tx-muted">{collection}</span>
            {report && (
              <Badge variant={report.status}>{report.status}</Badge>
            )}
          </div>
          {report && (
            <p className="text-xs text-tx-muted mt-0.5">
              latency: <span className="font-mono">{report.latency_ms.toFixed(1)}ms</span>
            </p>
          )}
        </div>
        <Button
          variant="ghost"
          size="sm"
          onClick={onCheck}
          disabled={loading}
          className="shrink-0"
        >
          {loading ? <Spinner size="sm" /> : <RefreshCw size={13} />}
          {loading ? "Checking…" : "Check"}
        </Button>
      </div>

      {/* Findings */}
      {report && report.findings.length > 0 && (
        <div className="flex flex-col gap-2">
          {report.findings.map((f, i) => (
            <FindingCard key={`${f.code}-${i}`} finding={f} />
          ))}
        </div>
      )}

      {/* Stats */}
      {report && <StatsSection report={report} />}
    </Card>
  );
}

// ── Panel ─────────────────────────────────────────────────────────────────────

export function IndexHealth() {
  const { backends, collections } = useVaraStore();

  const [reports, setReports] = useState<Record<string, HealthReport>>({});
  const [loading, setLoading] = useState<Record<string, boolean>>({});
  const [errors,  setErrors]  = useState<Record<string, string>>({});

  function resolveCollection(backendName: string): string {
    return collections.find((c) => c.backend_name === backendName)?.name ?? "";
  }

  const checkOne = useCallback(
    async (backendName: string) => {
      const col = resolveCollection(backendName);
      if (!col) return;

      setLoading((prev) => ({ ...prev, [backendName]: true }));
      setErrors((prev) => { const n = { ...prev }; delete n[backendName]; return n; });

      try {
        const report = await getHealth(backendName, col);
        setReports((prev) => ({ ...prev, [backendName]: report }));
      } catch (e) {
        setErrors((prev) => ({
          ...prev,
          [backendName]: e instanceof Error ? e.message : "Unknown error",
        }));
      } finally {
        setLoading((prev) => ({ ...prev, [backendName]: false }));
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [collections],
  );

  const checkAll = useCallback(() => {
    backends.forEach((b) => checkOne(b.name));
  }, [backends, checkOne]);

  if (backends.length === 0) {
    return (
      <EmptyState
        message="No backends loaded"
        sub="Make sure the Vara server is running and /api/config is reachable."
      />
    );
  }

  return (
    <div className="flex flex-col gap-6">
      {/* Panel header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-tx-primary">Index Health</h1>
          <p className="text-xs text-tx-muted mt-0.5">
            {backends.length} backend{backends.length !== 1 ? "s" : ""} configured
          </p>
        </div>
        <Button variant="ghost" size="sm" onClick={checkAll}>
          <RefreshCw size={13} />
          Check All
        </Button>
      </div>

      {/* Backend cards */}
      <div className="flex flex-col gap-4">
        {backends.map((b) => {
          const col = resolveCollection(b.name);
          return (
            <div key={b.name}>
              <BackendCard
                backend={b.name}
                collection={col || "— select a collection —"}
                report={reports[b.name] ?? null}
                loading={loading[b.name] ?? false}
                onCheck={() => checkOne(b.name)}
              />
              {errors[b.name] && (
                <p className="mt-1 text-xs text-sev-error px-1">{errors[b.name]}</p>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
