// TypeScript mirrors of vara backend Pydantic models

export interface BackendStatus {
  name: string;
  type: string;
}

export interface ConfigResponse {
  version: string;
  backends: BackendStatus[];
}

export interface CollectionInfo {
  name: string;
  vector_count: number;
  dimension: number;
  distance_metric: string;
  backend_name: string;
}

export interface CollectionsResponse {
  collections: CollectionInfo[];
}
