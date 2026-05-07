import { create } from "zustand";
import type { BackendStatus, CollectionInfo } from "../api/types";

type VlensState = {
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

export const useVlensStore = create<VlensState>((set) => ({
  backends: [],
  collections: [],
  setBackends: (backends) => set({ backends }),
  setCollections: (collections) => set({ collections }),

  explorerSeedIds: [],
  explorerSeedBackend: "",
  setExplorerSeed: (ids, backend) => set({ explorerSeedIds: ids, explorerSeedBackend: backend }),
  clearExplorerSeed: () => set({ explorerSeedIds: [], explorerSeedBackend: "" }),
}));
