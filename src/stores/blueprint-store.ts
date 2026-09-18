import { createStore } from 'zustand';
import type { Blueprint } from '@/types';

export interface BlueprintStore {
  selectedBlueprint: Blueprint | null;
  setSelectedBlueprint: (blueprint: Blueprint | null) => void;
  fetchBlueprintById: (id: string) => Promise<Blueprint>;
  fetchBlueprintByMd5: (md5: string) => Promise<Blueprint>;
  configSelections: Record<string, Blueprint>;
  setConfigSelection: (key: string, blueprint: Blueprint | null) => void;
  clearConfigSelections: () => void;
}

export const createBlueprintStore = () => {
  return createStore<BlueprintStore>((set, get) => ({
    selectedBlueprint: null,
    setSelectedBlueprint: (blueprint) => {
      if (blueprint !== get().selectedBlueprint) {
        set({ configSelections: {} });
      }
      set({ selectedBlueprint: blueprint });
    },
    fetchBlueprintById: async (id: string) => {
      const response = await fetch(`/api/blueprints/${id}`);
      if (!response.ok) {
        throw new Error('Failed to fetch blueprint');
      }
      return response.json();
    },
    fetchBlueprintByMd5: async (md5: string) => {
      const response = await fetch(`/api/blueprints/md5/${md5}`);
      if (!response.ok) {
        throw new Error('Failed to fetch blueprint');
      }
      return response.json();
    },
    configSelections: {},
    setConfigSelection: (key: string, blueprint: Blueprint | null) => {
      const currentSelections = get().configSelections;
      if (blueprint === null) {
        const { [key]: _unused, ...rest } = currentSelections;
        set({ configSelections: rest });
      } else {
        set({ configSelections: { ...currentSelections, [key]: blueprint } });
      }
    },
    clearConfigSelections: () => set({ configSelections: {} }),
  }));
};
