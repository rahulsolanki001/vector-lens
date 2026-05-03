import { useState, useRef, useCallback, useMemo, useEffect } from "react";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { OrbitControls } from "@react-three/drei";
import { EffectComposer, Bloom } from "@react-three/postprocessing";
import * as THREE from "three";
import { Layers, Play, Plus, X } from "lucide-react";
import type { ProjectionPoint } from "../api/types";
import { clusterProjection, connectProjectionWS } from "../api/client";
import { useVaraStore } from "../store";
import { Card } from "../components/ui/Card";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Input, Select } from "../components/ui/Input";
import { Spinner } from "../components/ui/Spinner";
import { EmptyState } from "../components/ui/EmptyState";

// ── Types ─────────────────────────────────────────────────────────────────────

type Status = "idle" | "running" | "complete" | "error";

// ── Color palette for payload groups ─────────────────────────────────────────

const NOISE_COLOR = "#374151"; // muted gray for HDBSCAN noise points (label -1)

const GROUP_PALETTE = [
  "#7C6AF7", // accent indigo
  "#34D399", // emerald
  "#FBBF24", // amber
  "#60A5FA", // sky
  "#F472B6", // pink
  "#A78BFA", // violet
  "#FB923C", // orange
  "#2DD4BF", // teal
  "#E879F9", // fuchsia
  "#94A3B8", // slate
];

function buildGroupColorMap(
  points: ProjectionPoint[],
  field: string,
): Record<string, string> {
  const values = Array.from(
    new Set(points.map((p) => String(p.payload?.[field] ?? "—"))),
  );
  const map: Record<string, string> = {};
  values.forEach((v, i) => {
    map[v] = GROUP_PALETTE[i % GROUP_PALETTE.length];
  });
  return map;
}

// ── Nearest neighbours in projected (normalised) space ───────────────────────

function kNearest(
  pts: { x: number; y: number; z: number }[],
  idx: number,
  k: number,
): number[] {
  const target = pts[idx];
  return pts
    .map((p, i) => ({
      i,
      d:
        (p.x - target.x) ** 2 +
        (p.y - target.y) ** 2 +
        (p.z - target.z) ** 2,
    }))
    .filter(({ i }) => i !== idx)
    .sort((a, b) => a.d - b.d)
    .slice(0, k)
    .map(({ i }) => i);
}

// ── Progress bar ──────────────────────────────────────────────────────────────

function ProgressBar({ value, max }: { value: number; max: number }) {
  const pct = max > 0 ? Math.min(100, (value / max) * 100) : 0;
  return (
    <div className="flex items-center gap-3">
      <div className="flex-1 h-1.5 bg-bg-border rounded-full overflow-hidden">
        <div
          className="h-full bg-accent rounded-full transition-all duration-300"
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="text-xs font-mono text-tx-secondary w-24 text-right shrink-0">
        {value} / {max} points
      </span>
    </div>
  );
}

// ── Point cloud ───────────────────────────────────────────────────────────────

interface NormPoint {
  id: string;
  x: number;
  y: number;
  z: number;
  payload: Record<string, unknown>;
}

interface PointCloudProps {
  points: NormPoint[];
  hoveredId: string | null;
  selectedId: string | null;
  colorMap: Record<string, string>; // id → hex color
  onHover: (id: string | null, pos: [number, number] | null) => void;
  onSelect: (id: string | null) => void;
  autoRotate: boolean;
  is2D: boolean;
}

function PointCloud({
  points,
  hoveredId,
  selectedId,
  colorMap,
  onHover,
  onSelect,
  autoRotate,
  is2D,
}: PointCloudProps) {
  const { camera, gl } = useThree();
  const prevHoveredRef = useRef<string | null>(null);
  const fittedRef      = useRef(false);

  // Build main points mesh
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
      // Brighten hovered / selected
      const brightness =
        p.id === selectedId ? 2.5 : p.id === hoveredId ? 1.8 : 1.0;
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
      size: 0.12,
      vertexColors: true,
      sizeAttenuation: true,
      transparent: true,
      opacity: 0.95,
    });

    return {
      mainMesh: new THREE.Points(geo, mat),
      normPositions: points,
      ids,
    };
  }, [points, hoveredId, selectedId, colorMap]);

  // Build neighbour lines for hovered point
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
    geo.setAttribute(
      "position",
      new THREE.BufferAttribute(new Float32Array(verts), 3),
    );
    const mat = new THREE.LineBasicMaterial({
      color: 0xffffff,
      transparent: true,
      opacity: 0.25,
    });
    return new THREE.LineSegments(geo, mat);
  }, [hoveredId, normPositions]);

  // Auto-fit camera once
  useEffect(() => {
    if (fittedRef.current || !mainMesh?.geometry.boundingSphere) return;
    fittedRef.current = true;
    const sphere = mainMesh.geometry.boundingSphere!;
    const cam    = camera as THREE.PerspectiveCamera;
    const dist   = (sphere.radius / Math.sin(((cam.fov / 2) * Math.PI) / 180)) * 1.5;
    camera.position.set(sphere.center.x, sphere.center.y, sphere.center.z + Math.max(dist, 5));
    camera.lookAt(sphere.center);
  }, [mainMesh, camera]);

  // Reset fit when points cleared
  useEffect(() => {
    if (points.length === 0) fittedRef.current = false;
  }, [points.length]);


  // Raycaster hover + click
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
        onHover(ids[idx], [
          ((pointer.x + 1) / 2) * rect.width,
          ((-pointer.y + 1) / 2) * rect.height,
        ]);
      }
    } else if (prevHoveredRef.current !== null) {
      prevHoveredRef.current = null;
      onHover(null, null);
    }
  });

  if (!mainMesh) return null;

  return (
    <>
      <OrbitControls
        makeDefault
        autoRotate={autoRotate && !is2D}
        autoRotateSpeed={0.6}
        enableRotate={!is2D}
      />
      <primitive object={mainMesh} onClick={(e: { stopPropagation: () => void }) => {
        e.stopPropagation();
        if (hoveredId) onSelect(hoveredId === selectedId ? null : hoveredId);
      }} />
      {neighbourLines && <primitive object={neighbourLines} />}
    </>
  );
}

// ── Hover tooltip ─────────────────────────────────────────────────────────────

function Tooltip({
  point,
  pos,
}: {
  point: ProjectionPoint;
  pos: [number, number];
}) {
  const entries = Object.entries(point.payload ?? {}).slice(0, 3);
  return (
    <div
      className="absolute pointer-events-none z-20 bg-bg-surface/95 border border-bg-border rounded-lg p-2.5 text-xs shadow-xl max-w-[240px] backdrop-blur-sm"
      style={{ left: pos[0] + 14, top: pos[1] - 10 }}
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

// ── Selected point side panel ─────────────────────────────────────────────────

function SelectionPanel({
  point,
  color,
  onClose,
}: {
  point: ProjectionPoint;
  color: string;
  onClose: () => void;
}) {
  const entries = Object.entries(point.payload ?? {});
  return (
    <div className="absolute right-0 top-0 bottom-0 w-64 bg-bg-surface/95 border-l border-bg-border p-4 flex flex-col gap-3 backdrop-blur-sm z-10 overflow-y-auto">
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold text-tx-primary">Selected Point</span>
        <button onClick={onClose} className="text-tx-muted hover:text-tx-primary transition-colors">
          <X size={14} />
        </button>
      </div>
      <div className="flex items-center gap-2">
        <span
          className="w-3 h-3 rounded-full shrink-0"
          style={{ backgroundColor: color, boxShadow: `0 0 6px ${color}` }}
        />
        <code className="text-xs font-mono text-tx-code break-all">{point.id}</code>
      </div>
      <div className="flex flex-col gap-1.5 pt-2 border-t border-bg-border">
        {entries.length === 0 && (
          <p className="text-xs text-tx-muted">No payload fields</p>
        )}
        {entries.map(([k, v]) => (
          <div key={k}>
            <p className="text-xs text-tx-muted">{k}</p>
            <p className="text-xs text-tx-secondary break-all">{String(v)}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Color legend ──────────────────────────────────────────────────────────────

function ColorLegend({
  groupMap,
  colorByField,
}: {
  groupMap: Record<string, string>;
  colorByField: string;
}) {
  const entries = Object.entries(groupMap).slice(0, 8);
  if (entries.length === 0) return null;
  return (
    <div className="absolute bottom-4 left-4 bg-bg-surface/80 border border-bg-border rounded-lg p-2.5 text-xs backdrop-blur-sm z-10 max-w-[160px]">
      <p className="text-tx-muted mb-1.5 font-medium">{colorByField}</p>
      <div className="flex flex-col gap-1">
        {entries.map(([val, color]) => (
          <div key={val} className="flex items-center gap-1.5">
            <span
              className="w-2.5 h-2.5 rounded-full shrink-0"
              style={{ backgroundColor: color, boxShadow: `0 0 4px ${color}` }}
            />
            <span className="text-tx-secondary truncate">{val}</span>
          </div>
        ))}
        {Object.keys(groupMap).length > 8 && (
          <p className="text-tx-muted mt-0.5">+{Object.keys(groupMap).length - 8} more</p>
        )}
      </div>
    </div>
  );
}

// ── HUD overlay ───────────────────────────────────────────────────────────────

function HUD({
  count,
  algorithm,
  viewMode,
  elapsedMs,
}: {
  count: number;
  algorithm: string;
  viewMode: "2d" | "3d";
  elapsedMs: number | null;
}) {
  return (
    <div className="absolute top-4 right-4 bg-bg-surface/80 border border-bg-border rounded-lg px-3 py-2 text-xs backdrop-blur-sm z-10 flex flex-col gap-0.5 text-right">
      <span className="text-tx-secondary font-mono">{count} points</span>
      <span className="text-tx-muted">{algorithm.toUpperCase()} · {viewMode.toUpperCase()}</span>
      {elapsedMs != null && (
        <span className="text-tx-muted">{(elapsedMs / 1000).toFixed(1)}s</span>
      )}
    </div>
  );
}

// ── Panel ─────────────────────────────────────────────────────────────────────

export function VectorExplorer() {
  const { backends, collections, explorerSeedIds, explorerSeedBackend, clearExplorerSeed } = useVaraStore();

  const hadSeed = useRef(explorerSeedIds.length > 0);

  // Controls — pre-populated from QueryDebugger jump if seed is present
  const initBackend = explorerSeedIds.length > 0 && explorerSeedBackend
    ? explorerSeedBackend
    : backends[0]?.name ?? "";

  const [idsText,        setIdsText]        = useState(
    explorerSeedIds.length > 0 ? explorerSeedIds.join(", ") : ""
  );
  const [backendName,    setBackendName]    = useState(initBackend);
  const [collectionName, setCollectionName] = useState(
    () => collections.find((c) => c.backend_name === initBackend)?.name ?? ""
  );
  const [algorithm,    setAlgorithm]    = useState<"umap" | "tsne">("umap");
  const [viewMode,     setViewMode]     = useState<"3d" | "2d">("3d");
  const [nNeighbors,   setNNeighbors]   = useState("15");
  const [minDist,      setMinDist]      = useState("0.1");
  const [colorByField, setColorByField] = useState("tenant_id");

  const collectionOptions = collections
    .filter((c) => c.backend_name === backendName)
    .map((c) => ({ value: c.name, label: c.name }));

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
  const [clusterLabels,    setClusterLabels]    = useState<Record<string, number> | null>(null);
  const [clusterStats,     setClusterStats]     = useState<{ n_clusters: number; noise_count: number } | null>(null);
  const [colorMode,        setColorMode]        = useState<"field" | "cluster">("field");
  const [minClusterSize,   setMinClusterSize]   = useState("5");
  const [clusterLoading,   setClusterLoading]   = useState(false);

  // Interaction state
  const [hoveredId,  setHoveredId]  = useState<string | null>(null);
  const [hoveredPt,  setHoveredPt]  = useState<ProjectionPoint | null>(null);
  const [tooltipPos, setTooltipPos] = useState<[number, number] | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [autoRotate, setAutoRotate] = useState(true);

  const closeWS = useRef<(() => void) | null>(null);

  // Normalise coordinates to [-2,2] cube
  const normPoints: NormPoint[] = useMemo(() => {
    if (rawPoints.length === 0) return [];
    const xs = rawPoints.map((p) => p.x);
    const ys = rawPoints.map((p) => p.y);
    const zs = rawPoints.map((p) => p.z);
    const cx = (Math.min(...xs) + Math.max(...xs)) / 2;
    const cy = (Math.min(...ys) + Math.max(...ys)) / 2;
    const cz = (Math.min(...zs) + Math.max(...zs)) / 2;
    const span = Math.max(
      Math.max(...xs) - Math.min(...xs),
      Math.max(...ys) - Math.min(...ys),
      Math.max(...zs) - Math.min(...zs),
      0.001,
    );
    const s = 4 / span;
    return rawPoints.map((p) => ({
      id: p.id,
      x: (p.x - cx) * s,
      y: (p.y - cy) * s,
      z: (p.z - cz) * s,
      payload: p.payload,
    }));
  }, [rawPoints]);

  // Group → color per payload value
  const groupColorMap = useMemo(
    () => buildGroupColorMap(normPoints, colorByField),
    [normPoints, colorByField],
  );

  // id → color map for PointCloud (switches between field and cluster modes)
  const idColorMap = useMemo(() => {
    const map: Record<string, string> = {};
    normPoints.forEach((p) => {
      if (colorMode === "cluster" && clusterLabels) {
        const label = clusterLabels[p.id] ?? -1;
        map[p.id] = label === -1 ? NOISE_COLOR : GROUP_PALETTE[label % GROUP_PALETTE.length];
      } else {
        const val = String(p.payload?.[colorByField] ?? "—");
        map[p.id] = groupColorMap[val] ?? GROUP_PALETTE[0];
      }
    });
    return map;
  }, [normPoints, groupColorMap, colorByField, colorMode, clusterLabels]);

  // Legend entries + label — switches with colorMode
  const legendEntries = useMemo(() => {
    if (colorMode === "cluster" && clusterLabels) {
      const seen = new Set(Object.values(clusterLabels));
      const map: Record<string, string> = {};
      Array.from(seen)
        .sort((a, b) => a - b)
        .forEach((label) => {
          map[label === -1 ? "noise" : `cluster ${label}`] =
            label === -1 ? NOISE_COLOR : GROUP_PALETTE[label % GROUP_PALETTE.length];
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

  const handleHover = useCallback(
    (id: string | null, pos: [number, number] | null) => {
      setHoveredId(id);
      setTooltipPos(pos);
      setHoveredPt(id ? (rawPoints.find((p) => p.id === id) ?? null) : null);
    },
    [rawPoints],
  );

  const handlePointerDown = useCallback(() => setAutoRotate(false), []);

  const project = useCallback(
    (baseJobId?: string) => {

      console.log("calling project with job =>",baseJobId);
      console.log(idsText);
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
          collection:   collectionName,
          backend:      backendName,
          ids,
          algorithm,
          n_components: viewMode === "2d" ? 2 : 3,
          n_neighbors:  Number(nNeighbors),
          min_dist:     Number(minDist),
          ...(baseJobId ? { base_job_id: baseJobId } : {}),
        },
        (jid)  => setJobId(jid),
        (msg)  => {
          setRawPoints((prev) => [...prev, ...msg.points]);
          setProjected(msg.projected);
          setTotal(msg.total);
        },
        (_jid) => {
          setStatus("complete");
          setElapsedMs(Date.now() - now);
          closeWS.current = null;
        },
        (msg)  => {
          setErrorMsg(msg);
          setStatus("error");
          closeWS.current = null;
        },
      );
      closeWS.current = close;
    },
    [idsText, collectionName, backendName, algorithm, viewMode, nNeighbors, minDist],
  );

  // Auto-project when arriving via QueryDebugger jump (idsText already seeded at init)
  useEffect(() => {
    if (hadSeed.current) {
      hadSeed.current = false;
      clearExplorerSeed();
      project();
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const addMore = useCallback(() => {
    if (jobId) project(jobId);
  }, [jobId, project]);

  const backendOptions = backends.map((b) => ({ value: b.name, label: b.name }));
  const algoOptions = [
    { value: "umap", label: "UMAP" },
    { value: "tsne", label: "t-SNE" },
  ];

  const selectedPoint = selectedId
    ? rawPoints.find((p) => p.id === selectedId) ?? null
    : null;

  return (
    <div className="flex flex-col gap-4" style={{ height: "calc(100vh - 112px)" }}>
      <h1 className="text-xl font-semibold text-tx-primary shrink-0">Vector Explorer</h1>

      {/* ── Controls ── */}
      <Card className="shrink-0">
        <div className="flex flex-col gap-3">
          <div className="flex gap-3 flex-wrap">
            <div className="flex-1 min-w-[180px]">
              <Input
                label="Point IDs (comma-separated)"
                placeholder="0, 1, 2, 10, 42"
                value={idsText}
                onChange={(e) => setIdsText(e.target.value)}
                disabled={status === "running"}
              />
            </div>
            <div className="w-36 shrink-0">
              <Select
                label="Backend"
                options={backendOptions.length ? backendOptions : [{ value: "", label: "No backends" }]}
                value={backendName}
                onChange={(e) => handleBackendChange(e.target.value)}
                disabled={status === "running"}
              />
            </div>
            <div className="w-36 shrink-0">
              <Select
                label="Collection"
                options={collectionOptions.length ? collectionOptions : [{ value: "", label: "No collections" }]}
                value={collectionName}
                onChange={(e) => setCollectionName(e.target.value)}
                disabled={status === "running"}
              />
            </div>
            <div className="w-28 shrink-0">
              <Select
                label="Algorithm"
                options={algoOptions}
                value={algorithm}
                onChange={(e) => setAlgorithm(e.target.value as "umap" | "tsne")}
                disabled={status === "running"}
              />
            </div>
            <div className="w-28 shrink-0">
              <span className="text-xs text-tx-secondary block mb-1">Dimensions</span>
              <div className="flex gap-0.5 p-0.5 bg-bg-raised rounded-md">
                {(["3d", "2d"] as const).map((m) => (
                  <button
                    key={m}
                    disabled={status === "running"}
                    onClick={() => {
                      if (m !== viewMode) {
                        setViewMode(m);
                        setRawPoints([]);
                        setStatus("idle");
                        setJobId(null);
                        setSelectedId(null);
                      }
                    }}
                    className={`flex-1 py-1 text-xs rounded font-medium transition-colors ${
                      viewMode === m
                        ? "bg-accent text-white"
                        : "text-tx-secondary hover:text-tx-primary disabled:opacity-40"
                    }`}
                  >
                    {m.toUpperCase()}
                  </button>
                ))}
              </div>
            </div>
            <div className="w-28 shrink-0">
              <Input
                label="Color by field"
                placeholder="tenant_id"
                value={colorByField}
                onChange={(e) => setColorByField(e.target.value)}
              />
            </div>
          </div>

          <div className="flex gap-3 flex-wrap items-end">
            <div className="w-24 shrink-0">
              <Input
                label="n_neighbors"
                type="number"
                min={2}
                max={200}
                value={nNeighbors}
                onChange={(e) => setNNeighbors(e.target.value)}
                disabled={status === "running"}
              />
            </div>
            <div className="w-24 shrink-0">
              <Input
                label="min_dist"
                type="number"
                min={0}
                max={1}
                step={0.05}
                value={minDist}
                onChange={(e) => setMinDist(e.target.value)}
                disabled={status === "running"}
              />
            </div>
            <div className="flex items-end gap-2 flex-wrap">
              <Button onClick={() => project()} disabled={status === "running"}>
                {status === "running" ? <Spinner size="sm" /> : <Play size={14} />}
                {status === "running" ? "Projecting…" : "Project"}
              </Button>
              {jobId && status === "complete" && (
                <Button variant="ghost" onClick={addMore}>
                  <Plus size={14} />
                  Add More IDs
                </Button>
              )}
            </div>
          </div>

          <div className="flex items-center gap-3 flex-wrap">
            {status === "running"  && <Badge variant="info">running</Badge>}
            {status === "complete" && <Badge variant="healthy">complete — {rawPoints.length} points</Badge>}
            {status === "error"    && <Badge variant="error">error</Badge>}
            {jobId && <span className="text-xs font-mono text-tx-muted">job: {jobId}</span>}
            {errorMsg && <span className="text-xs text-sev-error">{errorMsg}</span>}
          </div>

          {(status === "running" || (status === "complete" && total > 0)) && (
            <ProgressBar value={projected} max={total} />
          )}

          {/* ── Cluster controls ── */}
          {status === "complete" && jobId && (
            <div className="flex items-end gap-3 flex-wrap pt-3 border-t border-bg-border">
              <div className="w-32 shrink-0">
                <Input
                  label="min cluster size"
                  type="number"
                  min={2}
                  value={minClusterSize}
                  onChange={(e) => setMinClusterSize(e.target.value)}
                  disabled={clusterLoading}
                />
              </div>
              <Button variant="ghost" onClick={runCluster} disabled={clusterLoading}>
                {clusterLoading ? <Spinner size="sm" /> : <Layers size={14} />}
                {clusterLoading ? "Clustering…" : "Cluster"}
              </Button>
              {clusterLabels && (
                <>
                  {clusterStats && (
                    <span className="text-xs text-tx-muted self-end pb-1.5">
                      {clusterStats.n_clusters} clusters · {clusterStats.noise_count} noise
                    </span>
                  )}
                  <div className="flex gap-0.5 p-0.5 bg-bg-raised rounded-md self-end">
                    {(["field", "cluster"] as const).map((m) => (
                      <button
                        key={m}
                        onClick={() => setColorMode(m)}
                        className={`px-2 py-1 text-xs rounded font-medium transition-colors ${
                          colorMode === m
                            ? "bg-accent text-white"
                            : "text-tx-secondary hover:text-tx-primary"
                        }`}
                      >
                        {m === "field" ? "By field" : "By cluster"}
                      </button>
                    ))}
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => {
                      setClusterLabels(null);
                      setClusterStats(null);
                      setColorMode("field");
                    }}
                  >
                    <X size={14} />
                    Clear
                  </Button>
                </>
              )}
            </div>
          )}
        </div>
      </Card>

      {/* ── 3D Canvas ── */}
      <div
        className="relative flex-1 rounded-lg overflow-hidden border border-bg-border bg-bg-surface"
        onPointerDown={handlePointerDown}
      >
        {normPoints.length === 0 && status === "idle" && (
          <div className="absolute inset-0 flex items-center justify-center">
            <EmptyState
              message="No projection yet"
              sub="Enter point IDs and click Project to visualise vectors in 3D."
            />
          </div>
        )}

        {normPoints.length === 0 && status === "running" && (
          <div className="absolute inset-0 flex items-center justify-center">
            <Spinner size="lg" />
          </div>
        )}

        {normPoints.length > 0 && (
          <>
            <Canvas
              camera={{ position: [0, 0, 8], fov: 60 }}
              style={{ background: "#0A0C14" }}
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
                <Bloom
                  luminanceThreshold={0.2}
                  luminanceSmoothing={0.9}
                  intensity={1.4}
                />
              </EffectComposer>
            </Canvas>

            {/* Overlays */}
            <HUD
              count={normPoints.length}
              algorithm={algorithm}
              viewMode={viewMode}
              elapsedMs={elapsedMs}
            />
            <ColorLegend groupMap={legendEntries} colorByField={legendLabel} />

            {/* Hover tooltip */}
            {hoveredPt && tooltipPos && !selectedId && (
              <Tooltip point={hoveredPt} pos={tooltipPos} />
            )}

            {/* Selection side panel */}
            {selectedPoint && (
              <SelectionPanel
                point={selectedPoint}
                color={idColorMap[selectedPoint.id] ?? GROUP_PALETTE[0]}
                onClose={() => setSelectedId(null)}
              />
            )}
          </>
        )}
      </div>
    </div>
  );
}
