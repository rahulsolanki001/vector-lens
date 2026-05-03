import { useState } from "react";
import { Copy, Check } from "lucide-react";

interface CodeBlockProps {
  code: string;
  language?: string;
  maxHeight?: string;
}

export function CodeBlock({ code, maxHeight = "320px" }: CodeBlockProps) {
  const [copied, setCopied] = useState(false);

  function handleCopy() {
    navigator.clipboard.writeText(code).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    });
  }

  return (
    <div className="relative rounded-md bg-bg-base border border-bg-border group">
      <button
        onClick={handleCopy}
        className="absolute top-2 right-2 p-1.5 rounded text-tx-muted hover:text-tx-primary hover:bg-bg-raised transition-colors opacity-0 group-hover:opacity-100"
        title="Copy"
      >
        {copied ? <Check size={12} /> : <Copy size={12} />}
      </button>
      <pre
        className="overflow-auto px-4 py-3 text-xs font-mono text-tx-code leading-relaxed"
        style={{ maxHeight, fontSize: "11.5px", lineHeight: "1.55" }}
      >
        <code>{code}</code>
      </pre>
    </div>
  );
}
