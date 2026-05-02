// TypeScript mirrors of vara backend Pydantic models.
// Keep field names identical to the Python side — no camelCase conversion.

// ── Config ────────────────────────────────────────────────────────────────────

export interface BackendStatus {
  name: string;
  type: string;
}

export interface ConfigResponse {
  version: string;
  backends: BackendStatus[];
}

// ── Collections ───────────────────────────────────────────────────────────────

export interface CollectionInfo {
  name: string;
  vector_count: number;
  dimension: number;
  distance_metric: string;
  backend_name: string;
}

export interface CollectionStats {
  name: string;
  backend_name: string;
  vector_count: number;
  dimension: number;
  distance_metric: string;
  disk_bytes: number | null;
  ram_bytes: number | null;
  segment_count: number | null;
  index_type: string | null;
  index_params: Record<string, unknown>;
  payload_indexes: string[];
  raw: Record<string, unknown>;
}

// ── Health ────────────────────────────────────────────────────────────────────

export type Severity = "error" | "warning" | "info";
export type HealthStatus = "healthy" | "degraded" | "unhealthy";

export interface HealthFinding {
  severity: Severity;
  code: string;
  message: string;
  detail: string;
  recommendation: string;
}

export interface HealthReport {
  backend_name: string;
  collection: string;
  status: HealthStatus;
  findings: HealthFinding[];
  stats: CollectionStats | null;
  latency_ms: number;
}

// ── Query ─────────────────────────────────────────────────────────────────────

export interface QueryHit {
  id: string;
  score: number;
  payload: Record<string, unknown>;
  vector: number[] | null;
}

export interface QueryResult {
  hits: QueryHit[];
  total_hits: number;
  backend_name: string;
  collection: string;
  latency_ms: number;
  native_query: Record<string, unknown>;
}

// ── Debug ─────────────────────────────────────────────────────────────────────

export interface BackendQueryResult {
  backend_name: string;
  backend_type: string;
  result: QueryResult;
}

export interface BackendQueryError {
  backend_name: string;
  backend_type: string;
  error: string;
}

export interface HitAlignment {
  id: string;
  present_in: string[];
  missing_from: string[];
  ranks: Record<string, number>;
  scores: Record<string, number>;
}

export interface QueryRequest {
  collection: string;
  vector: number[];
  top_k: number;
  filters: Record<string, unknown> | null;
  with_payload: boolean;
  with_vectors: boolean;
}

export interface DebugQueryResult {
  collection: string;
  request: QueryRequest;
  results: BackendQueryResult[];
  errors: BackendQueryError[];
  alignments: HitAlignment[];
  common_hit_ids: string[];
  unique_hit_ids_by_backend: Record<string, string[]>;
  missing_hit_ids_by_backend: Record<string, string[]>;
}

export interface BackendComparison {
  backend_a: string;
  backend_b: string;
  debug: DebugQueryResult;
  jaccard_similarity: number;
  rank_spearman: number | null;
  score_spearman: number | null;
}

// ── Diagnose ──────────────────────────────────────────────────────────────────

export interface DiagnosisFinding {
  severity: Severity;
  code: string;
  message: string;
  detail: string;
  recommendation: string;
}

export interface ExpectedDocumentDiagnosis {
  id: string;
  found: boolean;
  retrieved: boolean;
  rank: number | null;
  score: number | null;
  score_gap_to_top: number | null;
  payload: Record<string, unknown>;
  findings: DiagnosisFinding[];
}

export interface DiagnosisResult {
  backend_name: string;
  backend_type: string;
  collection: string;
  top_k: number;
  expected_ids: string[];
  retrieved_ids: string[];
  native_query: Record<string, unknown>;
  errors: string[];
  document_diagnoses: ExpectedDocumentDiagnosis[];
  summary: string;
}

// ── Eval ──────────────────────────────────────────────────────────────────────

export interface EvalProgress {
  completed: number;
  total: number;
  metrics: Record<string, number>;
  latency_ms: Record<string, number>;
}

export interface EvalRunResponse {
  job_id: string;
  total_queries: number;
}

// ── Projection ────────────────────────────────────────────────────────────────

export interface ProjectionParams {
  collection: string;
  backend: string;
  ids: string[];
  algorithm?: "umap" | "tsne";
  n_components?: number;
  n_neighbors?: number;
  min_dist?: number;
  metric?: string;
  perplexity?: number;
  n_iter?: number;
  batch_size?: number;
  base_job_id?: string;
}

export interface ProjectionPoint {
  id: string;
  x: number;
  y: number;
  z: number;
  payload: Record<string, unknown>;
}

// ── WebSocket message shapes ──────────────────────────────────────────────────

export type EvalWsMessage =
  | { type: "progress" } & EvalProgress
  | { type: "complete" }
  | { type: "error"; error: string };

export type ProjectionWsMessage =
  | { type: "started"; job_id: string }
  | { type: "batch"; points: ProjectionPoint[]; projected: number; total: number }
  | { type: "complete"; job_id: string }
  | { type: "error"; error: string };

// ── Clustering ────────────────────────────────────────────────────────────────

export interface ClusterRequest {
  min_cluster_size?: number;
  min_samples?: number | null;
}

export interface ClusterResponse {
  job_id: string;
  labels: Record<string, number>;  // -1 = noise
  n_clusters: number;
  noise_count: number;
}

// ── Request bodies ────────────────────────────────────────────────────────────

export interface DebugQueryRequest {
  vector: number[];
  collection: string;
  backend_names?: string[];
  top_k?: number;
  filters?: Record<string, unknown> | null;
  with_payload?: boolean;
  with_vectors?: boolean;
}

export interface CompareRequest {
  vector: number[];
  collection: string;
  backend_a: string;
  backend_b: string;
  top_k?: number;
  filters?: Record<string, unknown> | null;
}

export interface DiagnoseRequest {
  vector: number[];
  collection: string;
  backend_name: string;
  expected_ids: string[];
  filters?: Record<string, unknown> | null;
}

export interface EvalRunRequest {
  dataset_path: string;
  collection: string;
  backend_name: string;
  k?: number;
  metrics?: string[];
  dim_truncations?: number[];
}
