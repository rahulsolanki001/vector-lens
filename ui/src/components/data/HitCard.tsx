import { useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";
import type { QueryHit } from "../../api/types";
import { ScoreBar } from "../ui/ScoreBar";

interface HitCardProps {
  hit: QueryHit;
  rank: number;
  highlight?: "common" | "unique";
}

const highlightClass: Record<string, string> = {
  common: "border-sev-healthy/40 bg-sev-healthy/5",
  unique: "border-accent/40 bg-accent/5",
};

export function HitCard({ hit, rank, highlight }: HitCardProps) {
  const [open, setOpen] = useState(false);
  const payloadKeys = Object.keys(hit.payload ?? {});

  return (
    <div
      className={`rounded-lg border bg-bg-surface p-3 transition-colors ${
        highlight ? highlightClass[highlight] : "border-bg-border"
      }`}
    >
      <div className="flex items-center gap-2 mb-2">
        <span className="text-xs text-tx-muted w-5 text-right shrink-0">#{rank}</span>
        <span className="font-mono text-xs text-tx-code truncate flex-1">{hit.id}</span>
        <span className="text-xs font-mono text-tx-secondary">{hit.score.toFixed(4)}</span>
      </div>
      <ScoreBar value={hit.score} showLabel={false} />
      {payloadKeys.length > 0 && (
        <button
          onClick={() => setOpen((v) => !v)}
          className="flex items-center gap-1 mt-2 text-xs text-tx-muted hover:text-tx-secondary transition-colors"
        >
          {open ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
          {open ? "hide" : `${payloadKeys.length} payload field${payloadKeys.length !== 1 ? "s" : ""}`}
        </button>
      )}
      {open && (
        <pre className="mt-2 text-xs font-mono text-tx-code bg-bg-raised rounded p-2 overflow-auto max-h-40">
          {JSON.stringify(hit.payload, null, 2)}
        </pre>
      )}
    </div>
  );
}
