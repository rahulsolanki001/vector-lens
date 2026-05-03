import type { ReactNode } from "react";

interface EmptyStateProps {
  icon?: ReactNode;
  message: string;
  sub?: string;
}

export function EmptyState({ icon, message, sub }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center gap-4 py-14 text-center">
      {icon && (
        <div className="relative flex items-center justify-center">
          <div
            className="absolute w-16 h-16 rounded-full"
            style={{
              background:
                "radial-gradient(circle, rgba(139,125,255,0.12) 0%, transparent 70%)",
            }}
          />
          <div className="relative w-14 h-14 rounded-xl bg-bg-surface border border-bg-border flex items-center justify-center text-tx-muted">
            {icon}
          </div>
        </div>
      )}
      <div className="flex flex-col gap-1">
        <p className="text-tx-secondary text-sm font-medium">{message}</p>
        {sub && <p className="text-tx-muted text-xs max-w-xs">{sub}</p>}
      </div>
    </div>
  );
}
