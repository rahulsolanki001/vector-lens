import type { Severity, HealthStatus } from "../../api/types";

type BadgeVariant = Severity | HealthStatus | "default" | "vio" | "cy";

const variantClasses: Record<BadgeVariant, string> = {
  error:     "bg-sev-error/10 text-sev-error border-sev-error/30",
  warning:   "bg-sev-warning/10 text-sev-warning border-sev-warning/30",
  info:      "bg-sev-info/10 text-sev-info border-sev-info/30",
  healthy:   "bg-sev-healthy/10 text-sev-healthy border-sev-healthy/30",
  degraded:  "bg-sev-warning/10 text-sev-warning border-sev-warning/30",
  unhealthy: "bg-sev-error/10 text-sev-error border-sev-error/30",
  vio:       "bg-accent/10 text-accent border-accent/30",
  cy:        "bg-cy/10 text-cy border-cy/30",
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
      className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded font-mono text-xs border ${variantClasses[variant]} ${className}`}
    >
      <span className="w-1.5 h-1.5 rounded-full bg-current flex-shrink-0" />
      {children}
    </span>
  );
}
