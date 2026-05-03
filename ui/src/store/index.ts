import { create } from "zustand";
import type { BackendStatus, CollectionInfo } from "../api/types";

type VaraState = {
  backendName: string;
  collectionName: string;
  setBackendName: (name: string) => void;
  setCollectionName: (name: string) => void;

  backends: BackendStatus[];
  collections: CollectionInfo[];
  setBackends: (backends: BackendStatus[]) => void;
  setCollections: (collections: CollectionInfo[]) => void;

  // Explorer jump seed — set by QueryDebugger, consumed by VectorExplorer on mount
  explorerSeedIds: string[];
  explorerSeedBackend: string;
  setExplorerSeed: (ids: string[], backend: string) => void;
  clearExplorerSeed: () => void;
};

export const useVaraStore = create<VaraState>((set) => ({
  backendName: "",
  collectionName: "",
  setBackendName: (backendName) => set({ backendName }),
  setCollectionName: (collectionName) => set({ collectionName }),

  backends: [],
  collections: [],
  setBackends: (backends) => set({ backends }),
  setCollections: (collections) => set({ collections }),

  explorerSeedIds: [],
  explorerSeedBackend: "",
  setExplorerSeed: (ids, backend) => set({ explorerSeedIds: ids, explorerSeedBackend: backend }),
  clearExplorerSeed: () => set({ explorerSeedIds: [], explorerSeedBackend: "" }),
}));
