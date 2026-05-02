import { useVaraStore } from "../../store";

export function TopBar() {
  const { backends, collections, backendName, collectionName, setBackendName, setCollectionName } =
    useVaraStore();

  const visibleCollections = collections.filter(
    (c) => !backendName || c.backend_name === backendName,
  );

  const isConnected = backends.length > 0;

  return (
    <header className="fixed top-0 left-0 right-0 z-40 h-16 flex items-center gap-5 px-5 bg-bg-surface border-b border-bg-border">
      {/* Logo */}
      <span className="font-mono font-bold text-2xl text-accent tracking-tight select-none">
        vara
      </span>

      <div className="w-px h-6 bg-bg-border" />

      {/* Backend selector */}
      <div className="flex items-center gap-2">
        <label className="text-xs text-tx-muted">backend</label>
        <select
          value={backendName}
          onChange={(e) => {
            setBackendName(e.target.value);
            setCollectionName("");
          }}
          className="h-7 px-2 text-sm bg-bg-raised border border-bg-border rounded text-tx-primary focus:outline-none focus:border-accent"
        >
          <option value="">all</option>
          {backends.map((b) => (
            <option key={b.name} value={b.name}>
              {b.name}
            </option>
          ))}
        </select>
      </div>

      {/* Collection selector */}
      <div className="flex items-center gap-2">
        <label className="text-xs text-tx-muted">collection</label>
        <select
          value={collectionName}
          onChange={(e) => setCollectionName(e.target.value)}
          className="h-7 px-2 text-sm bg-bg-raised border border-bg-border rounded text-tx-primary focus:outline-none focus:border-accent"
        >
          <option value="">—</option>
          {visibleCollections.map((c) => (
            <option key={`${c.backend_name}:${c.name}`} value={c.name}>
              {c.name}
            </option>
          ))}
        </select>
      </div>

      {/* Spacer */}
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
