import { useEffect, useState } from "react";

interface ScoreBarProps {
  value: number; // 0–1
  showLabel?: boolean;
  className?: string;
}

export function ScoreBar({ value, showLabel = true, className = "" }: ScoreBarProps) {
  const [ready, setReady] = useState(false);
  useEffect(() => { setReady(true); }, []);

  const scale = ready ? Math.max(0, Math.min(1, value)) : 0;

  return (
    <div className={`flex items-center gap-2 ${className}`}>
      <div className="flex-1 h-1 bg-bg-border rounded-full overflow-hidden">
        <div
          className="h-full w-full rounded-full origin-left"
          style={{
            background: "var(--grad)",
            transform: `scaleX(${scale})`,
            transition: "transform 200ms ease-out",
          }}
        />
      </div>
      {showLabel && (
        <span className="text-xs font-mono text-tx-secondary w-10 text-right tabular-nums">
          {value.toFixed(3)}
        </span>
      )}
    </div>
  );
}
