import type { CollectionInfo, ConfigResponse } from "./types";

export const API_BASE = "/api";
export const WS_BASE = "/ws";

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) throw new Error(`${init?.method ?? "GET"} ${path}: ${res.status}`);
  return res.json() as Promise<T>;
}

export function getConfig(): Promise<ConfigResponse> {
  return apiFetch<ConfigResponse>("/config");
}

export function getCollections(): Promise<CollectionInfo[]> {
  return apiFetch<{ collections: CollectionInfo[] }>("/collections").then(
    (r) => r.collections,
  );
}
