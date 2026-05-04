import { useState, useRef, useCallback, useMemo, useEffect } from "react";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { OrbitControls } from "@react-three/drei";
import { EffectComposer, Bloom } from "@react-three/postprocessing";
import * as THREE from "three";
import { Layers, Play, Plus, X, Boxes } from "lucide-react";
import type { ProjectionPoint } from "../api/types";
import { clusterProjection, connectProjectionWS } from "../api/client";
import { useVaraStore } from "../store";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Input, Select } from "../components/ui/Input";
import { Spinner } from "../components/ui/Spinner";
import { Kicker } from "../components/ui/Kicker";
import { SegmentedControl } from "../components/ui/SegmentedControl";
import { EmptyState } from "../components/ui/EmptyState";

// ── Types ─────────────────────────────────────────────────────────────────────

type Status = "idle" | "running" | "complete" | "error";

// ── Color palette ─────────────────────────────────────────────────────────────

const NOISE_COLOR = "#374151";

const GROUP_PALETTE = [
  "#7C6AF7", "#34D399", "#FBBF24", "#60A5FA", "#F472B6",
  "#A78BFA", "#FB923C", "#2DD4BF", "#E879F9", "#94A3B8",
];

function buildGroupColorMap(points: ProjectionPoint[], field: string): Record<string, string> {
  const values = Array.from(new Set(points.map((p) => String(p.payload?.[field] ?? "—"))));
  const map: Record<string, string> = {};
  values.forEach((v, i) => { map[v] = GROUP_PALETTE[i % GROUP_PALETTE.length]; });
  return map;
}

// ── kNearest ─────────────────────────────────────────────────────────────────

function kNearest(pts: { x: number; y: number; z: number }[], idx: number, k: number): number[] {
  const target = pts[idx];
  return pts
    .map((p, i) => ({ i, d: (p.x - target.x) ** 2 + (p.y - target.y) ** 2 + (p.z - target.z) ** 2 }))
    .filter(({ i }) => i !== idx)
    .sort((a, b) => a.d - b.d)
    .slice(0, k)
    .map(({ i }) => i);
}

// ── Glass panel ───────────────────────────────────────────────────────────────

function GlassPanel({ className = "", children }: { className?: string; children: React.ReactNode }) {
  return (
    <div
      className={`absolute rounded-xl ${className}`}
      style={{
        background: "rgba(17, 20, 27, 0.82)",
        backdropFilter: "blur(14px)",
        WebkitBackdropFilter: "blur(14px)",
        border: "1px solid rgba(255,255,255,0.06)",
        boxShadow: "0 4px 32px rgba(0,0,0,0.55)",
      }}
    >
      {children}
    </div>
  );
}

// ── NormPoint ─────────────────────────────────────────────────────────────────

interface NormPoint { id: string; x: number; y: number; z: number; payload: Record<string, unknown>; }

// ── PointCloud ────────────────────────────────────────────────────────────────

interface PointCloudProps {
  points: NormPoint[];
  hoveredId: string | null;
  selectedId: string | null;
  colorMap: Record<string, string>;
  onHover: (id: string | null, pos: [number, number] | null) => void;
  onSelect: (id: string | null) => void;
  autoRotate: boolean;
  is2D: boolean;
}

function PointCloud({ points, hoveredId, selectedId, colorMap, onHover, onSelect, autoRotate, is2D }: PointCloudProps) {
  const { camera, gl } = useThree();
  const prevHoveredRef = useRef<string | null>(null);
  const fittedRef      = useRef(false);

  const { mainMesh, normPositions, ids } = useMemo(() => {
    if (points.length === 0)
      return { mainMesh: null, normPositions: [] as NormPoint[], ids: [] as string[] };

    const positions = new Float32Array(points.length * 3);
    const colors    = new Float32Array(points.length * 3);
    const ids: string[] = [];

    points.forEach((p, i) => {
      positions[i * 3]     = p.x;
      positions[i * 3 + 1] = p.y;
      positions[i * 3 + 2] = p.z;
      const hex = colorMap[p.id] ?? GROUP_PALETTE[0];
      const col = new THREE.Color(hex);
      const brightness = p.id === selectedId ? 2.5 : p.id === hoveredId ? 1.8 : 1.0;
      colors[i * 3]     = col.r * brightness;
      colors[i * 3 + 1] = col.g * brightness;
      colors[i * 3 + 2] = col.b * brightness;
      ids.push(p.id);
    });

    const geo = new THREE.BufferGeometry();
    geo.setAttribute("position", new THREE.BufferAttribute(positions, 3));
    geo.setAttribute("color",    new THREE.BufferAttribute(colors, 3));
    geo.computeBoundingSphere();

    const mat = new THREE.PointsMaterial({
      size: 0.12, vertexColors: true, sizeAttenuation: true, transparent: true, opacity: 0.95,
    });

    return { mainMesh: new THREE.Points(geo, mat), normPositions: points, ids };
  }, [points, hoveredId, selectedId, colorMap]);

  const neighbourLines = useMemo(() => {
    if (!hoveredId || normPositions.length < 2) return null;
    const idx = normPositions.findIndex((p) => p.id === hoveredId);
    if (idx < 0) return null;
    const neighbours = kNearest(normPositions, idx, Math.min(5, normPositions.length - 1));
    const verts: number[] = [];
    const src = normPositions[idx];
    neighbours.forEach((ni) => {
      const dst = normPositions[ni];
      verts.push(src.x, src.y, src.z, dst.x, dst.y, dst.z);
    });
    const geo = new THREE.BufferGeometry();
    geo.setAttribute("position", new THREE.BufferAttribute(new Float32Array(verts), 3));
    const mat = new THREE.LineBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0.25 });
    return new THREE.LineSegments(geo, mat);
  }, [hoveredId, normPositions]);

  useEffect(() => {
    if (fittedRef.current || !mainMesh?.geometry.boundingSphere) return;
    fittedRef.current = true;
    const sphere = mainMesh.geometry.boundingSphere!;
    const cam = camera as THREE.PerspectiveCamera;
    const dist = (sphere.radius / Math.sin(((cam.fov / 2) * Math.PI) / 180)) * 1.5;
    camera.position.set(sphere.center.x, sphere.center.y, sphere.center.z + Math.max(dist, 5));
    camera.lookAt(sphere.center);
  }, [mainMesh, camera]);

  useEffect(() => { if (points.length === 0) fittedRef.current = false; }, [points.length]);

  useFrame(({ pointer }) => {
    if (!mainMesh || points.length === 0) return;
    const raycaster = new THREE.Raycaster();
    raycaster.params.Points = { threshold: 0.15 };
    raycaster.setFromCamera(pointer, camera);
    const hits = raycaster.intersectObject(mainMesh);
    if (hits.length > 0) {
      const idx = hits[0].index ?? -1;
      if (idx >= 0 && ids[idx] !== prevHoveredRef.current) {
        prevHoveredRef.current = ids[idx];
        const rect = gl.domElement.getBoundingClientRect();
        onHover(ids[idx], [((pointer.x + 1) / 2) * rect.width, ((-pointer.y + 1) / 2) * rect.height]);
      }
    } else if (prevHoveredRef.current !== null) {
      prevHoveredRef.current = null;
      onHover(null, null);
    }
  });

  if (!mainMesh) return null;

  return (
    <>
      <OrbitControls makeDefault autoRotate={autoRotate && !is2D} autoRotateSpeed={0.6} enableRotate={!is2D} />
      <primitive object={mainMesh} onClick={(e: { stopPropagation: () => void }) => {
        e.stopPropagation();
        if (hoveredId) onSelect(hoveredId === selectedId ? null : hoveredId);
      }} />
      {neighbourLines && <primitive object={neighbourLines} />}
    </>
  );
}

// ── Hover tooltip ─────────────────────────────────────────────────────────────

function Tooltip({ point, pos }: { point: ProjectionPoint; pos: [number, number] }) {
  const entries = Object.entries(point.payload ?? {}).slice(0, 3);
  return (
    <div
      className="absolute pointer-events-none z-30 rounded-lg p-2.5 text-xs max-w-[220px]"
      style={{
        left: pos[0] + 14,
        top: pos[1] - 10,
        background: "rgba(17, 20, 27, 0.92)",
        backdropFilter: "blur(10px)",
        border: "1px solid rgba(255,255,255,0.07)",
        boxShadow: "0 4px 16px rgba(0,0,0,0.5)",
      }}
    >
      <p className="font-mono text-tx-code truncate mb-1.5">{point.id}</p>
      {entries.map(([k, v]) => (
        <div key={k} className="flex gap-1.5">
          <span className="text-tx-muted shrink-0">{k}:</span>
          <span className="text-tx-secondary truncate">{String(v)}</span>
        </div>
      ))}
    </div>
  );
}

// ── Color legend ──────────────────────────────────────────────────────────────

function ColorLegend({ groupMap, colorByField }: { groupMap: Record<string, string>; colorByField: string }) {
  const entries = Object.entries(groupMap).slice(0, 8);
  if (entries.length === 0) return null;
  return (
    <GlassPanel className="bottom-4 left-4 z-20 p-2.5 max-w-[160px]">
      <p className="text-[10px] font-mono uppercase tracking-[0.06em] text-tx-muted mb-1.5">{colorByField}</p>
      <div className="flex flex-col gap-1">
        {entries.map(([val, color]) => (
          <div key={val} className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full shrink-0" style={{ backgroundColor: color, boxShadow: `0 0 4px ${color}` }} />
            <span className="text-[11px] text-tx-secondary truncate">{val}</span>
          </div>
        ))}
        {Object.keys(groupMap).length > 8 && (
          <p className="text-[10px] text-tx-muted mt-0.5">+{Object.keys(groupMap).length - 8} more</p>
        )}
      </div>
    </GlassPanel>
  );
}

// ── HUD ───────────────────────────────────────────────────────────────────────

function HUD({ count, algorithm, viewMode, elapsedMs }: {
  count: number; algorithm: string; viewMode: "2d" | "3d"; elapsedMs: number | null;
}) {
  return (
    <GlassPanel className="top-4 right-4 z-20 px-3 py-2 flex flex-col gap-0.5 text-right">
      <span className="text-xs font-mono text-tx-secondary tabular-nums">{count.toLocaleString()} pts</span>
      <span className="text-[11px] font-mono text-tx-muted">{algorithm.toUpperCase()} · {viewMode.toUpperCase()}</span>
      {elapsedMs != null && (
        <span className="text-[11px] font-mono text-tx-muted">{(elapsedMs / 1000).toFixed(1)}s</span>
      )}
    </GlassPanel>
  );
}

// ── Progress bar ──────────────────────────────────────────────────────────────

function ProgressBar({ value, max }: { value: number; max: number }) {
  const pct = max > 0 ? Math.min(100, (value / max) * 100) : 0;
  return (
    <div className="flex flex-col gap-1">
      <div className="h-1 bg-bg-border rounded-full overflow-hidden">
        <div className="h-full rounded-full transition-all duration-300" style={{ width: `${pct}%`, background: "var(--grad)" }} />
      </div>
      <span className="text-[10px] font-mono text-tx-muted text-right">{value} / {max} pts</span>
    </div>
  );
}

// ── Selection drawer (slides up from bottom) ──────────────────────────────────

function SelectionDrawer({ point, color, onClose }: { point: ProjectionPoint; color: string; onClose: () => void }) {
  const entries = Object.entries(point.payload ?? {});
  return (
    <div
      className="absolute left-4 right-4 bottom-4 z-20 rounded-xl p-4 max-h-[45%] overflow-y-auto"
      style={{
        background: "rgba(17, 20, 27, 0.90)",
        backdropFilter: "blur(16px)",
        WebkitBackdropFilter: "blur(16px)",
        border: "1px solid rgba(255,255,255,0.07)",
        boxShadow: "0 -4px 32px rgba(0,0,0,0.5), 0 4px 32px rgba(0,0,0,0.4)",
        animation: "slideUp 220ms cubic-bezier(0.4,0,0.2,1)",
      }}
    >
      <style>{`@keyframes slideUp { from { transform: translateY(24px); opacity: 0; } to { transform: translateY(0); opacity: 1; } }`}</style>
      <div className="flex items-start justify-between gap-3 mb-3">
        <div className="flex items-center gap-2 min-w-0">
          <span className="w-3 h-3 rounded-full shrink-0" style={{ backgroundColor: color, boxShadow: `0 0 6px ${color}` }} />
          <code className="text-xs font-mono text-tx-code break-all">{point.id}</code>
        </div>
        <button onClick={onClose} className="text-tx-muted hover:text-tx-primary transition-colors shrink-0">
          <X size={14} />
        </button>
      </div>
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-x-6 gap-y-2 pt-2 border-t border-bg-border">
        {entries.length === 0 && <p className="text-xs text-tx-muted col-span-full">No payload fields</p>}
        {entries.map(([k, v]) => (
          <div key={k}>
            <p className="text-[10px] font-mono uppercase tracking-[0.05em] text-tx-muted">{k}</p>
            <p className="text-xs text-tx-secondary break-all">{String(v)}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Panel ─────────────────────────────────────────────────────────────────────

const ALGO_OPTIONS: { value: "umap" | "tsne"; label: string }[] = [
  { value: "umap", label: "UMAP" },
  { value: "tsne", label: "t-SNE" },
];

const DIM_OPTIONS: { value: "3d" | "2d"; label: string }[] = [
  { value: "3d", label: "3D" },
  { value: "2d", label: "2D" },
];

const COLOR_OPTIONS: { value: "field" | "cluster"; label: string }[] = [
  { value: "field",   label: "By field" },
  { value: "cluster", label: "By cluster" },
];

export function VectorExplorer() {
  const { backends, collections, explorerSeedIds, explorerSeedBackend, clearExplorerSeed } = useVaraStore();
  const hadSeed = useRef(explorerSeedIds.length > 0);

  const initBackend = explorerSeedIds.length > 0 && explorerSeedBackend
    ? explorerSeedBackend
    : backends[0]?.name ?? "";

  const [idsText,        setIdsText]        = useState(explorerSeedIds.length > 0 ? explorerSeedIds.join(", ") : "");
  const [backendName,    setBackendName]    = useState(initBackend);
  const [collectionName, setCollectionName] = useState(
    () => collections.find((c) => c.backend_name === initBackend)?.name ?? ""
  );
  const [algorithm,    setAlgorithm]    = useState<"umap" | "tsne">("umap");
  const [viewMode,     setViewMode]     = useState<"3d" | "2d">("3d");
  const [nNeighbors,   setNNeighbors]   = useState("15");
  const [minDist,      setMinDist]      = useState("0.1");
  const [colorByField, setColorByField] = useState("tenant_id");

  const collectionOptions = collections.filter((c) => c.backend_name === backendName).map((c) => ({ value: c.name, label: c.name }));
  const backendOptions = backends.map((b) => ({ value: b.name, label: b.name }));

  function handleBackendChange(name: string) {
    setBackendName(name);
    setCollectionName(collections.find((c) => c.backend_name === name)?.name ?? "");
  }

  // Run state
  const [status,    setStatus]    = useState<Status>("idle");
  const [rawPoints, setRawPoints] = useState<ProjectionPoint[]>([]);
  const [projected, setProjected] = useState(0);
  const [total,     setTotal]     = useState(0);
  const [jobId,     setJobId]     = useState<string | null>(null);
  const [errorMsg,  setErrorMsg]  = useState<string | null>(null);
  const [elapsedMs, setElapsedMs] = useState<number | null>(null);

  // Cluster state
  const [clusterLabels,  setClusterLabels]  = useState<Record<string, number> | null>(null);
  const [clusterStats,   setClusterStats]   = useState<{ n_clusters: number; noise_count: number } | null>(null);
  const [colorMode,      setColorMode]      = useState<"field" | "cluster">("field");
  const [minClusterSize, setMinClusterSize] = useState("5");
  const [clusterLoading, setClusterLoading] = useState(false);

  // Interaction state
  const [hoveredId,  setHoveredId]  = useState<string | null>(null);
  const [hoveredPt,  setHoveredPt]  = useState<ProjectionPoint | null>(null);
  const [tooltipPos, setTooltipPos] = useState<[number, number] | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [autoRotate, setAutoRotate] = useState(true);

  const closeWS = useRef<(() => void) | null>(null);

  // Normalise to [-2,2] cube
  const normPoints: NormPoint[] = useMemo(() => {
    if (rawPoints.length === 0) return [];
    const xs = rawPoints.map((p) => p.x);
    const ys = rawPoints.map((p) => p.y);
    const zs = rawPoints.map((p) => p.z);
    const cx = (Math.min(...xs) + Math.max(...xs)) / 2;
    const cy = (Math.min(...ys) + Math.max(...ys)) / 2;
    const cz = (Math.min(...zs) + Math.max(...zs)) / 2;
    const span = Math.max(Math.max(...xs) - Math.min(...xs), Math.max(...ys) - Math.min(...ys), Math.max(...zs) - Math.min(...zs), 0.001);
    const s = 4 / span;
    return rawPoints.map((p) => ({ id: p.id, x: (p.x - cx) * s, y: (p.y - cy) * s, z: (p.z - cz) * s, payload: p.payload }));
  }, [rawPoints]);

  const groupColorMap = useMemo(() => buildGroupColorMap(normPoints, colorByField), [normPoints, colorByField]);

  const idColorMap = useMemo(() => {
    const map: Record<string, string> = {};
    normPoints.forEach((p) => {
      if (colorMode === "cluster" && clusterLabels) {
        const label = clusterLabels[p.id] ?? -1;
        map[p.id] = label === -1 ? NOISE_COLOR : GROUP_PALETTE[label % GROUP_PALETTE.length];
      } else {
        map[p.id] = groupColorMap[String(p.payload?.[colorByField] ?? "—")] ?? GROUP_PALETTE[0];
      }
    });
    return map;
  }, [normPoints, groupColorMap, colorByField, colorMode, clusterLabels]);

  const legendEntries = useMemo(() => {
    if (colorMode === "cluster" && clusterLabels) {
      const seen = new Set(Object.values(clusterLabels));
      const map: Record<string, string> = {};
      Array.from(seen).sort((a, b) => a - b).forEach((label) => {
        map[label === -1 ? "noise" : `cluster ${label}`] = label === -1 ? NOISE_COLOR : GROUP_PALETTE[label % GROUP_PALETTE.length];
      });
      return map;
    }
    return groupColorMap;
  }, [colorMode, clusterLabels, groupColorMap]);

  const legendLabel = colorMode === "cluster" ? "clusters" : colorByField;

  const runCluster = useCallback(async () => {
    if (!jobId) return;
    setClusterLoading(true);
    try {
      const res = await clusterProjection(jobId, { min_cluster_size: Number(minClusterSize) });
      setClusterLabels(res.labels);
      setClusterStats({ n_clusters: res.n_clusters, noise_count: res.noise_count });
      setColorMode("cluster");
    } catch (e) {
      setErrorMsg(e instanceof Error ? e.message : "Clustering failed");
    } finally {
      setClusterLoading(false);
    }
  }, [jobId, minClusterSize]);

  const handleHover = useCallback((id: string | null, pos: [number, number] | null) => {
    setHoveredId(id);
    setTooltipPos(pos);
    setHoveredPt(id ? (rawPoints.find((p) => p.id === id) ?? null) : null);
  }, [rawPoints]);

  const handlePointerDown = useCallback(() => setAutoRotate(false), []);

  const project = useCallback((baseJobId?: string) => {
    const ids = idsText.split(",").map((s) => s.trim()).filter(Boolean);
    if (ids.length === 0) { setErrorMsg("Enter at least one ID"); return; }
    if (!collectionName)  { setErrorMsg("Select a collection first"); return; }
    if (!backendName)     { setErrorMsg("Select a backend"); return; }

    setErrorMsg(null);
    setStatus("running");
    setAutoRotate(true);
    setSelectedId(null);
    const now = Date.now();
    setElapsedMs(null);

    if (!baseJobId) {
      setRawPoints([]);
      setProjected(0);
      setTotal(0);
      setJobId(null);
      setClusterLabels(null);
      setClusterStats(null);
      setColorMode("field");
    }

    const close = connectProjectionWS(
      {
        collection: collectionName, backend: backendName, ids, algorithm,
        n_components: viewMode === "2d" ? 2 : 3,
        n_neighbors: Number(nNeighbors), min_dist: Number(minDist),
        ...(baseJobId ? { base_job_id: baseJobId } : {}),
      },
      (jid)  => setJobId(jid),
      (msg)  => { setRawPoints((prev) => [...prev, ...msg.points]); setProjected(msg.projected); setTotal(msg.total); },
      (_jid) => { setStatus("complete"); setElapsedMs(Date.now() - now); closeWS.current = null; },
      (msg)  => { setErrorMsg(msg); setStatus("error"); closeWS.current = null; },
    );
    closeWS.current = close;
  }, [idsText, collectionName, backendName, algorithm, viewMode, nNeighbors, minDist]);

  useEffect(() => {
    if (hadSeed.current) {
      hadSeed.current = false;
      clearExplorerSeed();
      project();
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const addMore = useCallback(() => { if (jobId) project(jobId); }, [jobId, project]);

  const selectedPoint = selectedId ? rawPoints.find((p) => p.id === selectedId) ?? null : null;

  return (
    <div className="-mx-6 -mt-6 relative overflow-hidden" style={{ height: "calc(100vh - 64px)" }}>

      {/* ── Full-area canvas with radial gradient backdrop ── */}
      <div className="absolute inset-0" onPointerDown={handlePointerDown}>
        {normPoints.length > 0 ? (
          <Canvas
            camera={{ position: [0, 0, 8], fov: 60 }}
            style={{ background: "radial-gradient(ellipse at 50% 55%, rgba(139,125,255,0.09) 0%, #0B0D12 65%)" }}
            gl={{ antialias: true, toneMapping: THREE.ACESFilmicToneMapping }}
          >
            <PointCloud
              points={normPoints}
              hoveredId={hoveredId}
              selectedId={selectedId}
              colorMap={idColorMap}
              onHover={handleHover}
              onSelect={setSelectedId}
              autoRotate={autoRotate}
              is2D={viewMode === "2d"}
            />
            <EffectComposer>
              <Bloom luminanceThreshold={0.2} luminanceSmoothing={0.9} intensity={1.4} />
            </EffectComposer>
          </Canvas>
        ) : (
          <div
            className="w-full h-full flex items-center justify-center"
            style={{ background: "radial-gradient(ellipse at 50% 55%, rgba(139,125,255,0.06) 0%, #0B0D12 65%)" }}
          >
            {status === "running" ? (
              <Spinner size="lg" />
            ) : (
              <div className="pointer-events-none">
                <EmptyState
                  icon={<Boxes size={22} />}
                  message="Nothing projected yet"
                  sub="Enter point IDs in the panel on the left and click Project to visualise vectors."
                />
              </div>
            )}
          </div>
        )}
      </div>

      {/* ── Controls glass panel — top-left ── */}
      <GlassPanel className="top-4 left-4 z-20 w-72 flex flex-col gap-3 p-4">
        {/* Header */}
        <div className="flex items-center justify-between">
          <Kicker>Vector Explorer</Kicker>
          <div className="flex items-center gap-1.5">
            {status === "running"  && <Badge variant="vio">running</Badge>}
            {status === "complete" && <Badge variant="healthy">done</Badge>}
            {status === "error"    && <Badge variant="error">error</Badge>}
          </div>
        </div>

        {/* IDs */}
        <div className="flex flex-col gap-1">
          <Kicker>Point IDs</Kicker>
          <textarea
            className="w-full bg-bg-raised border border-bg-border rounded-md px-3 py-2 text-xs font-mono text-tx-primary placeholder:text-tx-muted resize-none focus:outline-none focus:ring-[3px] focus:ring-accent/20 focus:border-accent/60 transition-shadow"
            rows={2}
            placeholder="0, 1, 2, 10, 42"
            value={idsText}
            onChange={(e) => setIdsText(e.target.value)}
            disabled={status === "running"}
          />
        </div>

        {/* Backend + collection */}
        <Select
          label="Backend"
          options={backendOptions.length ? backendOptions : [{ value: "", label: "No backends" }]}
          value={backendName}
          onChange={(e) => handleBackendChange(e.target.value)}
          disabled={status === "running"}
        />
        <Select
          label="Collection"
          options={collectionOptions.length ? collectionOptions : [{ value: "", label: "No collections" }]}
          value={collectionName}
          onChange={(e) => setCollectionName(e.target.value)}
          disabled={status === "running"}
        />

        {/* Algorithm + dimensions */}
        <div className="grid grid-cols-2 gap-2">
          <div className="flex flex-col gap-1">
            <Kicker>Algorithm</Kicker>
            <SegmentedControl options={ALGO_OPTIONS} value={algorithm} onChange={setAlgorithm} />
          </div>
          <div className="flex flex-col gap-1">
            <Kicker>Dimensions</Kicker>
            <SegmentedControl
              options={DIM_OPTIONS}
              value={viewMode}
              onChange={(v) => {
                if (v !== viewMode) {
                  setViewMode(v);
                  setRawPoints([]);
                  setStatus("idle");
                  setJobId(null);
                  setSelectedId(null);
                }
              }}
            />
          </div>
        </div>

        {/* Color by field */}
        <Input
          label="Color by field"
          placeholder="tenant_id"
          value={colorByField}
          onChange={(e) => setColorByField(e.target.value)}
        />

        {/* UMAP params */}
        <div className="grid grid-cols-2 gap-2">
          <Input label="n_neighbors" type="number" min={2} max={200} value={nNeighbors}
            onChange={(e) => setNNeighbors(e.target.value)} disabled={status === "running"} />
          <Input label="min_dist" type="number" min={0} max={1} step={0.05} value={minDist}
            onChange={(e) => setMinDist(e.target.value)} disabled={status === "running"} />
        </div>

        {errorMsg && <p className="text-[11px] text-sev-error">{errorMsg}</p>}

        {/* Actions */}
        <div className="flex gap-2 flex-wrap">
          <Button onClick={() => project()} disabled={status === "running"} className="flex-1">
            {status === "running" ? <Spinner size="sm" /> : <Play size={13} />}
            {status === "running" ? "Projecting…" : "Project"}
          </Button>
          {jobId && status === "complete" && (
            <Button variant="ghost" onClick={addMore}>
              <Plus size={13} />
              More
            </Button>
          )}
        </div>

        {/* Progress */}
        {(status === "running" || (status === "complete" && total > 0)) && (
          <ProgressBar value={projected} max={total} />
        )}

        {/* Cluster controls */}
        {status === "complete" && jobId && (
          <div className="flex flex-col gap-2 pt-2 border-t border-bg-border">
            <Kicker>Clustering</Kicker>
            <div className="flex gap-2 items-end">
              <div className="flex-1">
                <Input label="min size" type="number" min={2} value={minClusterSize}
                  onChange={(e) => setMinClusterSize(e.target.value)} disabled={clusterLoading} />
              </div>
              <Button variant="ghost" onClick={runCluster} disabled={clusterLoading}>
                {clusterLoading ? <Spinner size="sm" /> : <Layers size={13} />}
                Cluster
              </Button>
            </div>
            {clusterLabels && (
              <div className="flex flex-col gap-1.5">
                {clusterStats && (
                  <p className="text-[11px] text-tx-muted">{clusterStats.n_clusters} clusters · {clusterStats.noise_count} noise</p>
                )}
                <div className="flex gap-1.5 items-center">
                  <SegmentedControl options={COLOR_OPTIONS} value={colorMode} onChange={setColorMode} />
                  <button onClick={() => { setClusterLabels(null); setClusterStats(null); setColorMode("field"); }}
                    className="text-tx-muted hover:text-tx-primary transition-colors">
                    <X size={13} />
                  </button>
                </div>
              </div>
            )}
          </div>
        )}
      </GlassPanel>

      {/* ── HUD — top-right ── */}
      {normPoints.length > 0 && (
        <HUD count={normPoints.length} algorithm={algorithm} viewMode={viewMode} elapsedMs={elapsedMs} />
      )}

      {/* ── Color legend — bottom-left ── */}
      {normPoints.length > 0 && !selectedPoint && (
        <ColorLegend groupMap={legendEntries} colorByField={legendLabel} />
      )}

      {/* ── Hover tooltip ── */}
      {hoveredPt && tooltipPos && !selectedId && (
        <Tooltip point={hoveredPt} pos={tooltipPos} />
      )}

      {/* ── Selection drawer — slides up from bottom ── */}
      {selectedPoint && (
        <SelectionDrawer
          point={selectedPoint}
          color={idColorMap[selectedPoint.id] ?? GROUP_PALETTE[0]}
          onClose={() => setSelectedId(null)}
        />
      )}
    </div>
  );
}
