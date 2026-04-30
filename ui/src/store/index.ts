import { create } from "zustand";

type VaraState = {
  backendName: string;
  collectionName: string;
  setBackendName: (backendName: string) => void;
  setCollectionName: (collectionName: string) => void;
};

export const useVaraStore = create<VaraState>((set) => ({
  backendName: "",
  collectionName: "",
  setBackendName: (backendName) => set({ backendName }),
  setCollectionName: (collectionName) => set({ collectionName })
}));
