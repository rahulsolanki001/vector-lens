import type { ReactNode } from "react";

interface CardProps {
  children: ReactNode;
  className?: string;
}

export function Card({ children, className = "" }: CardProps) {
  return (
    <div className={`bg-bg-surface border border-bg-border rounded-lg p-4 ${className}`}>
      {children}
    </div>
  );
}
