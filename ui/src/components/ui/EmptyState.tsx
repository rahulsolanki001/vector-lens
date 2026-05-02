import type { ReactNode } from "react";

interface EmptyStateProps {
  icon?: ReactNode;
  message: string;
  sub?: string;
}

export function EmptyState({ icon, message, sub }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-12 text-center">
      {icon && <div className="text-tx-muted opacity-60">{icon}</div>}
      <p className="text-tx-secondary text-sm font-medium">{message}</p>
      {sub && <p className="text-tx-muted text-xs">{sub}</p>}
    </div>
  );
}
