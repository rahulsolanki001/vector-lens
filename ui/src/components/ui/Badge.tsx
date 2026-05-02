import type { Severity, HealthStatus } from "../../api/types";

type BadgeVariant = Severity | HealthStatus | "default";

const variantClasses: Record<BadgeVariant, string> = {
  error:     "bg-sev-error/15 text-sev-error border-sev-error/30",
  warning:   "bg-sev-warning/15 text-sev-warning border-sev-warning/30",
  info:      "bg-sev-info/15 text-sev-info border-sev-info/30",
  healthy:   "bg-sev-healthy/15 text-sev-healthy border-sev-healthy/30",
  degraded:  "bg-sev-warning/15 text-sev-warning border-sev-warning/30",
  unhealthy: "bg-sev-error/15 text-sev-error border-sev-error/30",
  default:   "bg-bg-raised text-tx-secondary border-bg-border",
};

interface BadgeProps {
  variant?: BadgeVariant;
  children: React.ReactNode;
  className?: string;
}

export function Badge({ variant = "default", children, className = "" }: BadgeProps) {
  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium border ${variantClasses[variant]} ${className}`}
    >
      {children}
    </span>
  );
}
