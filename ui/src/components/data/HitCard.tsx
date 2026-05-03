import { useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";
import type { QueryHit } from "../../api/types";
import { ScoreBar } from "../ui/ScoreBar";
import { CodeBlock } from "../ui/CodeBlock";

interface HitCardProps {
  hit: QueryHit;
  rank: number;
  highlight?: "common" | "unique";
}

const rankColor = (r: number) =>
  r <= 3 ? "text-sev-healthy" : r <= 8 ? "text-sev-warning" : "text-tx-muted";

const borderColor: Record<string, string> = {
  common: "border-l-2 border-sev-healthy",
  unique: "border-l-2 border-accent",
};

export function HitCard({ hit, rank, highlight }: HitCardProps) {
  const [open, setOpen] = useState(false);
  const payloadKeys = Object.keys(hit.payload ?? {});
  const previewEntry = Object.entries(hit.payload ?? {}).find(([, v]) => typeof v === "string");
  const preview = previewEntry ? String(previewEntry[1]).slice(0, 72) : null;

  return (
    <div>
      <div
        className={`flex items-center gap-3 px-3 py-2 rounded-lg hover:bg-bg-raised transition-colors ${
          highlight ? borderColor[highlight] : ""
        }`}
      >
        {/* Rank */}
        <span className={`font-mono text-xs font-semibold w-5 text-right shrink-0 tabular-nums ${rankColor(rank)}`}>
          {rank}
        </span>

        {/* ID + payload preview */}
        <div className="flex-1 min-w-0">
          <span className="font-mono text-xs text-tx-code block truncate">{hit.id}</span>
          {preview && (
            <span className="text-xs text-tx-secondary truncate block leading-tight mt-0.5">{preview}</span>
          )}
        </div>

        {/* Score + bar */}
        <div className="flex flex-col items-end gap-1 w-24 shrink-0">
          <span className="font-mono text-xs text-tx-secondary tabular-nums">{hit.score.toFixed(4)}</span>
          <ScoreBar value={hit.score} showLabel={false} className="w-full" />
        </div>

        {/* Expand toggle */}
        {payloadKeys.length > 0 && (
          <button
            onClick={() => setOpen((v) => !v)}
            className="text-tx-muted hover:text-tx-secondary transition-colors shrink-0"
          >
            {open ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
          </button>
        )}
      </div>

      {open && (
        <div className="mx-8 mb-1">
          <CodeBlock code={JSON.stringify(hit.payload, null, 2)} maxHeight="160px" />
        </div>
      )}
    </div>
  );
}
