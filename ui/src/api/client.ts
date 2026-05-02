import type {
  BackendComparison,
  ClusterRequest,
  ClusterResponse,
  CollectionInfo,
  ConfigResponse,
  DebugQueryRequest,
  DebugQueryResult,
  DiagnoseRequest,
  DiagnosisResult,
  CompareRequest,
  EvalRunRequest,
  EvalRunResponse,
  EvalProgress,
  EvalWsMessage,
  HealthReport,
  ProjectionParams,
  ProjectionWsMessage,
} from "./types";

export const API_BASE = "/api";
export const WS_BASE = "/ws";

// ── Core fetch helper ─────────────────────────────────────────────────────────

async function apiFetch<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(`${init?.method ?? "GET"} ${path} → ${res.status}: ${text}`);
  }
  return res.json() as Promise<T>;
}

function post<T>(path: string, body: unknown): Promise<T> {
  return apiFetch<T>(path, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

// ── Config ────────────────────────────────────────────────────────────────────

export function getConfig(): Promise<ConfigResponse> {
  return apiFetch<ConfigResponse>("/config");
}

// ── Collections ───────────────────────────────────────────────────────────────

export function getCollections(): Promise<CollectionInfo[]> {
  return apiFetch<{ collections: CollectionInfo[] }>("/collections").then(
    (r) => r.collections,
  );
}

// ── Health ────────────────────────────────────────────────────────────────────

export function getHealth(backend: string, collection: string): Promise<HealthReport> {
  return apiFetch<HealthReport>(`/collections/${encodeURIComponent(backend)}/${encodeURIComponent(collection)}/health`);
}

// ── Query ─────────────────────────────────────────────────────────────────────

export function debugQuery(req: DebugQueryRequest): Promise<DebugQueryResult> {
  return post<DebugQueryResult>("/query/debug", req);
}

export function compareQuery(req: CompareRequest): Promise<BackendComparison> {
  return post<BackendComparison>("/query/compare", req);
}

export function diagnoseQuery(req: DiagnoseRequest): Promise<DiagnosisResult> {
  return post<DiagnosisResult>("/query/diagnose", req);
}

// ── Eval ──────────────────────────────────────────────────────────────────────

export function startEval(req: EvalRunRequest): Promise<EvalRunResponse> {
  return post<EvalRunResponse>("/eval/run", req);
}

export function connectEvalWS(
  jobId: string,
  onProgress: (p: EvalProgress) => void,
  onComplete: () => void,
  onError: (msg: string) => void,
): () => void {
  const ws = new WebSocket(`${WS_BASE}/eval/${jobId}`);

  ws.onmessage = (e) => {
    const msg = JSON.parse(e.data as string) as EvalWsMessage;
    if (msg.type === "progress") {
      const { type: _t, ...progress } = msg;
      onProgress(progress as EvalProgress);
    } else if (msg.type === "complete") {
      onComplete();
      ws.close();
    } else if (msg.type === "error") {
      onError(msg.error);
      ws.close();
    }
  };

  ws.onerror = () => onError("WebSocket connection error");

  return () => ws.close();
}

// ── Projection ────────────────────────────────────────────────────────────────

export function clusterProjection(jobId: string, req: ClusterRequest): Promise<ClusterResponse> {
  return post<ClusterResponse>(`/projection/${encodeURIComponent(jobId)}/cluster`, req);
}

export function connectProjectionWS(
  params: ProjectionParams,
  onStarted: (jobId: string) => void,
  onBatch: (points: ProjectionWsMessage & { type: "batch" }) => void,
  onComplete: (jobId: string) => void,
  onError: (msg: string) => void,
): () => void {
  const ws = new WebSocket(`${WS_BASE}/projection`);

  ws.onopen = () => {
    ws.send(JSON.stringify(params));
  };

  ws.onmessage = (e) => {
    const msg = JSON.parse(e.data as string) as ProjectionWsMessage;
    if (msg.type === "started") {
      onStarted(msg.job_id);
    } else if (msg.type === "batch") {
      onBatch(msg);
    } else if (msg.type === "complete") {
      onComplete(msg.job_id);
      ws.close();
    } else if (msg.type === "error") {
      onError(msg.error);
      ws.close();
    }
  };

  ws.onerror = () => onError("WebSocket connection error");

  return () => ws.close();
}
