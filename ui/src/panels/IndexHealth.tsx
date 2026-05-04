import { useState, useCallback } from "react";
import { RefreshCw, CheckCircle2, AlertTriangle, XCircle, Info } from "lucide-react";
import type { HealthFinding, HealthReport, HealthStatus } from "../api/types";
import { getHealth } from "../api/client";
import { useVaraStore } from "../store";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Spinner } from "../components/ui/Spinner";
import { EmptyState } from "../components/ui/EmptyState";
import { Kicker } from "../components/ui/Kicker";

// ── Status orb ────────────────────────────────────────────────────────────────

const orbConfig: Record<HealthStatus, { bg: string; ring: string; icon: React.ReactNode }> = {
  healthy: {
    bg: "bg-sev-healthy/10",
    ring: "ring-1 ring-sev-healthy/30",
    icon: <CheckCircle2 size={16} className="text-sev-healthy" />,
  },
  degraded: {
    bg: "bg-sev-warning/10",
    ring: "ring-1 ring-sev-warning/30",
    icon: <AlertTriangle size={16} className="text-sev-warning" />,
  },
  unhealthy: {
    bg: "bg-sev-error/10",
    ring: "ring-1 ring-sev-error/30",
    icon: <XCircle size={16} className="text-sev-error" />,
  },
};

function StatusOrb({ status }: { status: HealthStatus }) {
  const cfg = orbConfig[status];
  return (
    <div
      className={`w-8 h-8 rounded-md flex items-center justify-center shrink-0 ${cfg.bg} ${cfg.ring}`}
    >
      {cfg.icon}
    </div>
  );
}

// ── Stats grid ────────────────────────────────────────────────────────────────

function StatsGrid({ report }: { report: HealthReport }) {
  const s = report.stats;
  if (!s) return null;

  const cells = [
    { label: "Vectors",   value: s.vector_count != null ? s.vector_count.toLocaleString() : null },
    { label: "Dimension", value: s.dimension != null ? String(s.dimension) : null },
    { label: "Distance",  value: s.distance_metric ?? null },
    { label: "Index",     value: s.index_type ?? null },
    {
      label: "Disk",
      value: s.disk_bytes != null ? `${(s.disk_bytes / 1024 / 1024).toFixed(1)} MB` : null,
    },
    {
      label: "RAM",
      value: s.ram_bytes != null ? `${(s.ram_bytes / 1024 / 1024).toFixed(1)} MB` : null,
    },
  ].filter((c) => c.value !== null) as { label: string; value: string }[];

  if (cells.length === 0) return null;

  return (
    <div className="grid grid-cols-2 gap-px bg-bg-border rounded-lg overflow-hidden">
      {cells.map(({ label, value }) => (
        <div key={label} className="bg-bg-base px-3 py-2.5">
          <div className="text-[10px] font-mono uppercase tracking-[0.06em] text-tx-muted mb-0.5">
            {label}
          </div>
          <div className="text-xs font-mono text-tx-primary tabular-nums">{value}</div>
        </div>
      ))}
    </div>
  );
}

// ── Finding row ───────────────────────────────────────────────────────────────

const findingIcons: Record<string, React.ReactNode> = {
  error:   <XCircle size={13} className="text-sev-error shrink-0 mt-0.5" />,
  warning: <AlertTriangle size={13} className="text-sev-warning shrink-0 mt-0.5" />,
  info:    <Info size={13} className="text-sev-info shrink-0 mt-0.5" />,
};

function FindingRow({ finding }: { finding: HealthFinding }) {
  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-start gap-2">
        {findingIcons[finding.severity]}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap mb-0.5">
            <code className="font-mono text-[10px] text-tx-muted">{finding.code}</code>
            <span className="text-xs text-tx-primary">{finding.message}</span>
          </div>
          {finding.detail && (
            <p className="text-xs text-tx-secondary">{finding.detail}</p>
          )}
        </div>
      </div>
      {finding.recommendation && (
        <div className="ml-5 border-l-2 border-accent bg-bg-raised rounded-r-md px-3 py-2">
          <p className="text-xs text-tx-secondary">{finding.recommendation}</p>
        </div>
      )}
    </div>
  );
}

// ── Backend card ──────────────────────────────────────────────────────────────

interface BackendCardProps {
  backend: string;
  collection: string;
  report: HealthReport | null;
  loading: boolean;
  error?: string;
  onCheck: () => void;
}

function BackendCard({ backend, collection, report, loading, error, onCheck }: BackendCardProps) {
  return (
    <div
      className="bg-bg-surface border border-bg-border rounded-xl flex flex-col gap-4 p-5"
      style={{ boxShadow: "inset 0 1px 0 rgba(255,255,255,0.04)" }}
    >
      {/* Header */}
      <div className="flex items-start gap-3">
        {report ? (
          <StatusOrb status={report.status} />
        ) : (
          <div className="w-8 h-8 rounded-md bg-bg-raised ring-1 ring-bg-border shrink-0" />
        )}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-sm font-semibold text-tx-primary">{backend}</span>
            {report && <Badge variant={report.status}>{report.status}</Badge>}
          </div>
          <span className="font-mono text-[11px] text-tx-muted">
            {collection || "— no collection —"}
          </span>
          {report && (
            <div className="text-[11px] text-tx-muted mt-0.5">
              latency{" "}
              <span className="font-mono text-tx-secondary">
                {report.latency_ms.toFixed(1)}ms
              </span>
            </div>
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

      {/* Stats */}
      {report?.stats && <StatsGrid report={report} />}

      {/* Findings */}
      {report && report.findings.length > 0 && (
        <div className="flex flex-col gap-3">
          <Kicker>Findings</Kicker>
          {report.findings.map((f, i) => (
            <FindingRow key={`${f.code}-${i}`} finding={f} />
          ))}
        </div>
      )}

      {/* All clear */}
      {report && report.findings.length === 0 && (
        <p className="text-xs text-tx-muted">No issues found.</p>
      )}

      {/* Error */}
      {error && <p className="text-xs text-sev-error">{error}</p>}
    </div>
  );
}

// ── Summary chips ─────────────────────────────────────────────────────────────

function SummaryChips({ reports }: { reports: Record<string, HealthReport> }) {
  const counts = Object.values(reports).reduce(
    (acc, r) => {
      acc[r.status] = (acc[r.status] ?? 0) + 1;
      return acc;
    },
    {} as Partial<Record<HealthStatus, number>>,
  );

  const order: HealthStatus[] = ["healthy", "degraded", "unhealthy"];

  return (
    <div className="flex items-center gap-2 flex-wrap">
      {order.map((s) =>
        counts[s] ? (
          <Badge key={s} variant={s}>
            {counts[s]} {s}
          </Badge>
        ) : null,
      )}
    </div>
  );
}

// ── Panel ─────────────────────────────────────────────────────────────────────

export function IndexHealth() {
  const { backends, collections } = useVaraStore();

  const [reports, setReports] = useState<Record<string, HealthReport>>({});
  const [loading, setLoading] = useState<Record<string, boolean>>({});
  const [errors, setErrors] = useState<Record<string, string>>({});

  function resolveCollection(backendName: string): string {
    return collections.find((c) => c.backend_name === backendName)?.name ?? "";
  }

  const checkOne = useCallback(
    async (backendName: string) => {
      const col = resolveCollection(backendName);
      if (!col) return;

      setLoading((prev) => ({ ...prev, [backendName]: true }));
      setErrors((prev) => {
        const n = { ...prev };
        delete n[backendName];
        return n;
      });

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

  const checkedCount = Object.keys(reports).length;

  return (
    <div className="flex flex-col gap-6">
      {/* Header */}
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div className="flex flex-col gap-1.5">
          <h1 className="text-xl font-semibold text-tx-primary">Index Health</h1>
          {checkedCount > 0 ? (
            <SummaryChips reports={reports} />
          ) : (
            <p className="text-xs text-tx-muted">
              {backends.length} backend{backends.length !== 1 ? "s" : ""} configured — run a check to see status
            </p>
          )}
        </div>
        <Button variant="ghost" size="sm" onClick={checkAll}>
          <RefreshCw size={13} />
          Check All
        </Button>
      </div>

      {/* Auto-fill grid */}
      <div
        className="grid gap-4"
        style={{ gridTemplateColumns: "repeat(auto-fill, minmax(360px, 1fr))" }}
      >
        {backends.map((b) => {
          const col = resolveCollection(b.name);
          return (
            <BackendCard
              key={b.name}
              backend={b.name}
              collection={col}
              report={reports[b.name] ?? null}
              loading={loading[b.name] ?? false}
              error={errors[b.name]}
              onCheck={() => checkOne(b.name)}
            />
          );
        })}
      </div>
    </div>
  );
}
