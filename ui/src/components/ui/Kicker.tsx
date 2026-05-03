import type { ReactNode } from "react";

interface KickerProps {
  children: ReactNode;
  className?: string;
}

export function Kicker({ children, className = "" }: KickerProps) {
  return (
    <span
      className={`font-mono text-xs uppercase tracking-[0.08em] text-tx-muted select-none ${className}`}
    >
      {children}
    </span>
  );
}
