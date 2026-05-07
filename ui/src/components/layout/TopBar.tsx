import { useVlensStore } from "../../store";

export function TopBar() {
  const { backends } = useVlensStore();
  const isConnected = backends.length > 0;

  return (
    <header className="fixed top-0 left-0 right-0 z-40 h-16 flex items-center gap-5 px-5 bg-bg-surface border-b border-bg-border">
      {/* Logo */}
      <span className="font-mono font-bold text-2xl text-accent tracking-tight select-none">
        Vector Lens
      </span>

      <div className="flex-1" />

      {/* Connection status */}
      <div className="flex items-center gap-1.5">
        <span
          className={`w-2 h-2 rounded-full ${isConnected ? "bg-sev-healthy" : "bg-sev-error"}`}
        />
        <span className="text-xs text-tx-muted">
          {isConnected ? `${backends.length} backend${backends.length > 1 ? "s" : ""}` : "disconnected"}
        </span>
      </div>
    </header>
  );
}
