interface ScoreBarProps {
  value: number; // 0–1
  showLabel?: boolean;
  className?: string;
}

export function ScoreBar({ value, showLabel = true, className = "" }: ScoreBarProps) {
  const pct = Math.max(0, Math.min(1, value)) * 100;
  return (
    <div className={`flex items-center gap-2 ${className}`}>
      <div className="flex-1 h-1.5 bg-bg-border rounded-full overflow-hidden">
        <div
          className="h-full bg-accent rounded-full transition-all"
          style={{ width: `${pct}%` }}
        />
      </div>
      {showLabel && (
        <span className="text-xs font-mono text-tx-secondary w-10 text-right">
          {value.toFixed(3)}
        </span>
      )}
    </div>
  );
}
