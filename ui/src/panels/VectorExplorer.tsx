import { useState, useRef, useCallback, useMemo, useEffect } from "react";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { OrbitControls } from "@react-three/drei";
import * as THREE from "three";
import { Play, Plus } from "lucide-react";
import type { ProjectionPoint } from "../api/types";
import { connectProjectionWS } from "../api/client";
import { useVaraStore } from "../store";
import { Card } from "../components/ui/Card";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Input, Select } from "../components/ui/Input";
import { Spinner } from "../components/ui/Spinner";
import { EmptyState } from "../components/ui/EmptyState";

// ── Types ─────────────────────────────────────────────────────────────────────

type Status = "idle" | "running" | "complete" | "error";

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

// ── Point cloud (Three.js) ────────────────────────────────────────────────────

const ACCENT_COLOR  = new THREE.Color("#7C6AF7");
const HOVERED_COLOR = new THREE.Color("#F87171");

interface PointCloudProps {
  points: ProjectionPoint[];
  hoveredId: string | null;
  onHover: (id: string | null, pos: [number, number] | null) => void;
}

function PointCloud({ points, hoveredId, onHover }: PointCloudProps) {
  const { camera, gl } = useThree();
  const prevHoveredRef = useRef<string | null>(null);
  const fittedRef      = useRef(false);

  // Normalise coordinates to a [-2, 2] cube so the fixed camera always sees them
  const { threePoints, ids } = useMemo(() => {
    if (points.length === 0) return { threePoints: null, ids: [] };

    const xs = points.map((p) => p.x);
    const ys = points.map((p) => p.y);
    const zs = points.map((p) => p.z);
    const cx = (Math.min(...xs) + Math.max(...xs)) / 2;
    const cy = (Math.min(...ys) + Math.max(...ys)) / 2;
    const cz = (Math.min(...zs) + Math.max(...zs)) / 2;
    const span = Math.max(
      Math.max(...xs) - Math.min(...xs),
      Math.max(...ys) - Math.min(...ys),
      Math.max(...zs) - Math.min(...zs),
      0.001,
    );
    const scale = 4 / span;

    const positions = new Float32Array(points.length * 3);
    const colors    = new Float32Array(points.length * 3);
    const ids: string[] = [];

    points.forEach((p, i) => {
      positions[i * 3]     = (p.x - cx) * scale;
      positions[i * 3 + 1] = (p.y - cy) * scale;
      positions[i * 3 + 2] = (p.z - cz) * scale;

      const c = p.id === hoveredId ? HOVERED_COLOR : ACCENT_COLOR;
      colors[i * 3]     = c.r;
      colors[i * 3 + 1] = c.g;
      colors[i * 3 + 2] = c.b;

      ids.push(p.id);
    });

    const geo = new THREE.BufferGeometry();
    geo.setAttribute("position", new THREE.BufferAttribute(positions, 3));
    geo.setAttribute("color",    new THREE.BufferAttribute(colors, 3));
    geo.computeBoundingSphere();

    const mat = new THREE.PointsMaterial({
      size: 0.1,
      vertexColors: true,
      sizeAttenuation: true,
      transparent: true,
      opacity: 0.9,
    });

    return { threePoints: new THREE.Points(geo, mat), ids };
  }, [points, hoveredId]);

  // Reset camera fit flag when new projection starts
  useEffect(() => {
    fittedRef.current = false;
  }, [points.length === 0 ? 0 : 1]);

  // Fit camera to bounding sphere on first render
  useEffect(() => {
    if (fittedRef.current || !threePoints?.geometry.boundingSphere) return;
    fittedRef.current = true;
    const sphere = threePoints.geometry.boundingSphere;
    const cam = camera as THREE.PerspectiveCamera;
    const dist = (sphere.radius / Math.sin(((cam.fov / 2) * Math.PI) / 180)) * 1.5;
    camera.position.set(sphere.center.x, sphere.center.y, sphere.center.z + Math.max(dist, 5));
    camera.lookAt(sphere.center);
  }, [threePoints, camera]);

  // Raycaster — only calls onHover when hovered ID changes
  useFrame(({ pointer }) => {
    if (!threePoints || points.length === 0) return;
    const raycaster = new THREE.Raycaster();
    raycaster.params.Points = { threshold: 0.15 };
    raycaster.setFromCamera(pointer, camera);
    const intersects = raycaster.intersectObject(threePoints);
    if (intersects.length > 0) {
      const idx = intersects[0].index ?? -1;
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

  if (!threePoints) return null;
  return <primitive object={threePoints} />;
}

// ── Tooltip ───────────────────────────────────────────────────────────────────

interface TooltipProps {
  point: ProjectionPoint;
  pos: [number, number];
}

function Tooltip({ point, pos }: TooltipProps) {
  const payloadSnippet = Object.entries(point.payload ?? {})
    .slice(0, 3)
    .map(([k, v]) => `${k}: ${String(v).slice(0, 40)}`)
    .join("\n");

  return (
    <div
      className="absolute pointer-events-none z-10 bg-bg-surface border border-bg-border rounded-lg p-2 text-xs shadow-lg max-w-[220px]"
      style={{ left: pos[0] + 12, top: pos[1] - 8 }}
    >
      <p className="font-mono text-tx-code truncate mb-1">{point.id}</p>
      {payloadSnippet && (
        <pre className="text-tx-muted whitespace-pre-wrap">{payloadSnippet}</pre>
      )}
    </div>
  );
}

// ── Panel ─────────────────────────────────────────────────────────────────────

export function VectorExplorer() {
  const { backends, collectionName } = useVaraStore();

  // Controls
  const [idsText,     setIdsText]     = useState("");
  const [backendName, setBackendName] = useState(backends[0]?.name ?? "");
  const [algorithm,   setAlgorithm]   = useState<"umap" | "tsne">("umap");
  const [nNeighbors,  setNNeighbors]  = useState("15");
  const [minDist,     setMinDist]     = useState("0.1");

  // Run state
  const [status,    setStatus]    = useState<Status>("idle");
  const [points,    setPoints]    = useState<ProjectionPoint[]>([]);
  const [projected, setProjected] = useState(0);
  const [total,     setTotal]     = useState(0);
  const [jobId,     setJobId]     = useState<string | null>(null);
  const [errorMsg,  setErrorMsg]  = useState<string | null>(null);

  // Hover state
  const [hoveredId,  setHoveredId]  = useState<string | null>(null);
  const [hoveredPt,  setHoveredPt]  = useState<ProjectionPoint | null>(null);
  const [tooltipPos, setTooltipPos] = useState<[number, number] | null>(null);

  const closeWS = useRef<(() => void) | null>(null);

  const handleHover = useCallback(
    (id: string | null, pos: [number, number] | null) => {
      setHoveredId(id);
      setTooltipPos(pos);
      setHoveredPt(id ? (points.find((p) => p.id === id) ?? null) : null);
    },
    [points],
  );

  const project = useCallback(
    (baseJobId?: string) => {
      const ids = idsText.split(",").map((s) => s.trim()).filter(Boolean);
      if (ids.length === 0) { setErrorMsg("Enter at least one ID"); return; }
      if (!collectionName)  { setErrorMsg("Select a collection first"); return; }
      if (!backendName)     { setErrorMsg("Select a backend"); return; }

      setErrorMsg(null);
      setStatus("running");
      if (!baseJobId) {
        setPoints([]);
        setProjected(0);
        setTotal(0);
        setJobId(null);
      }

      const close = connectProjectionWS(
        {
          collection:  collectionName,
          backend:     backendName,
          ids,
          algorithm,
          n_neighbors: Number(nNeighbors),
          min_dist:    Number(minDist),
          ...(baseJobId ? { base_job_id: baseJobId } : {}),
        },
        (jid) => setJobId(jid),
        (msg) => {
          setPoints((prev) => [...prev, ...msg.points]);
          setProjected(msg.projected);
          setTotal(msg.total);
        },
        (_jid) => { setStatus("complete"); closeWS.current = null; },
        (msg)  => { setErrorMsg(msg); setStatus("error"); closeWS.current = null; },
      );

      closeWS.current = close;
    },
    [idsText, collectionName, backendName, algorithm, nNeighbors, minDist],
  );

  const addMore = useCallback(() => {
    if (jobId) project(jobId);
  }, [jobId, project]);

  const backendOptions = backends.map((b) => ({ value: b.name, label: b.name }));
  const algoOptions = [
    { value: "umap", label: "UMAP" },
    { value: "tsne", label: "t-SNE" },
  ];

  return (
    <div className="flex flex-col gap-4" style={{ height: "calc(100vh - 112px)" }}>
      <h1 className="text-xl font-semibold text-tx-primary shrink-0">Vector Explorer</h1>

      {/* ── Controls ── */}
      <Card className="shrink-0">
        <div className="flex flex-col gap-3">
          <div className="flex gap-3 flex-wrap">
            <div className="flex-1 min-w-[200px]">
              <Input
                label="Point IDs (comma-separated)"
                placeholder="0, 1, 2, 10, 42"
                value={idsText}
                onChange={(e) => setIdsText(e.target.value)}
                disabled={status === "running"}
              />
            </div>
            <div className="flex-1 min-w-[140px]">
              <Select
                label="Backend"
                options={backendOptions.length ? backendOptions : [{ value: "", label: "No backends" }]}
                value={backendName}
                onChange={(e) => setBackendName(e.target.value)}
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
          </div>

          <div className="flex gap-3 flex-wrap">
            <div className="w-28 shrink-0">
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
            <div className="w-28 shrink-0">
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
            <div className="flex items-end gap-2">
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

          {/* Status row */}
          <div className="flex items-center gap-3 flex-wrap">
            {status === "running"  && <Badge variant="info">running</Badge>}
            {status === "complete" && <Badge variant="healthy">complete — {points.length} points</Badge>}
            {status === "error"    && <Badge variant="error">error</Badge>}
            {jobId && <span className="text-xs font-mono text-tx-muted">job: {jobId}</span>}
            {errorMsg && <span className="text-xs text-sev-error">{errorMsg}</span>}
          </div>

          {(status === "running" || (status === "complete" && total > 0)) && (
            <ProgressBar value={projected} max={total} />
          )}
        </div>
      </Card>

      {/* ── 3D Canvas ── */}
      <div className="relative flex-1 rounded-lg overflow-hidden border border-bg-border bg-bg-surface">
        {points.length === 0 && status === "idle" && (
          <div className="absolute inset-0 flex items-center justify-center">
            <EmptyState
              message="No projection yet"
              sub="Enter point IDs and click Project to visualise vectors in 3D."
            />
          </div>
        )}

        {points.length === 0 && status === "running" && (
          <div className="absolute inset-0 flex items-center justify-center">
            <Spinner size="lg" />
          </div>
        )}

        {points.length > 0 && (
          <Canvas
            camera={{ position: [0, 0, 5], fov: 60 }}
            style={{ background: "#0F1117" }}
          >
            <ambientLight intensity={0.5} />
            <PointCloud
              points={points}
              hoveredId={hoveredId}
              onHover={handleHover}
            />
            <OrbitControls makeDefault />
          </Canvas>
        )}

        {/* Hover tooltip */}
        {hoveredPt && tooltipPos && (
          <Tooltip point={hoveredPt} pos={tooltipPos} />
        )}
      </div>
    </div>
  );
}
