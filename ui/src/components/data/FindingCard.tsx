import { AlertCircle, AlertTriangle, Info } from "lucide-react";
import type { HealthFinding, DiagnosisFinding } from "../../api/types";
import { Badge } from "../ui/Badge";

type AnyFinding = HealthFinding | DiagnosisFinding;

const icons = {
  error:   <AlertCircle size={14} className="text-sev-error shrink-0 mt-0.5" />,
  warning: <AlertTriangle size={14} className="text-sev-warning shrink-0 mt-0.5" />,
  info:    <Info size={14} className="text-sev-info shrink-0 mt-0.5" />,
};

interface FindingCardProps {
  finding: AnyFinding;
}

export function FindingCard({ finding }: FindingCardProps) {
  return (
    <div className="flex gap-3 rounded-lg border border-bg-border bg-bg-surface p-3">
      {icons[finding.severity]}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1">
          <Badge variant={finding.severity}>{finding.severity}</Badge>
          <code className="text-xs font-mono text-tx-muted">{finding.code}</code>
        </div>
        <p className="text-sm text-tx-primary mb-1">{finding.message}</p>
        {finding.detail && (
          <p className="text-xs text-tx-secondary mb-1">{finding.detail}</p>
        )}
        {finding.recommendation && (
          <p className="text-xs text-tx-muted italic">{finding.recommendation}</p>
        )}
      </div>
    </div>
  );
}
