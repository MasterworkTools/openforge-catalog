/*
  Data returned looks like:
  {
    tag_counts: {
      'tag1': 5,
      'tag1|tag2': 3,
      'tag1|tag4': 2,
      'tag1|tag2|tag3': 1,
    }
  }

  Resulting data structure:
  {
    tag1: {
      __count: 5,       <-- Note that there are no instances of the top level tags having a count
      __totalCount: 11,
      __subTags: 3,
      children: {
        tag2: {
          __count: 3,
          __totalCount: 4,
          __subTags: 1,
          children: {
            tag3: {
              __count: 1
            }
          }
        },
        tag4: {
          __count: 2
        }
      },
    },
    ...
  }
*/

import { createStore } from 'zustand';
import type { TagNode, Blueprint, Paging } from '@/types';
import { devLog } from '@/utils/log';

export interface TagStore {
  data: Record<string, TagNode>;
  expandedNodes: Record<string, boolean>;
  selectedTags: string[];
  denyTags: string[];
  blueprints: Blueprint[];
  paging: Paging | null;
  autoload: boolean;
  search_models: boolean;
  search_blueprints: boolean;
  searchTerm: string | null;
  tagDescriptions: Record<string, string>;
  initialSetupComplete: boolean;
  fetchData: () => Promise<void>;
  setData: (tagCounts: Record<string, number>) => void;
  toggleNode: (key: string) => void;
  addTag: (tag: string) => void;
  addAllTags: (tags: string[]) => void;
  removeTag: (tag: string) => void;
  clearTags: () => void;
  addDenyTag: (tag: string) => void;
  removeDenyTag: (tag: string) => void;
  setTagState: (tags: { require?: string[]; deny?: string[]; searchTerm?: string | null }) => void;
  fetchBlueprints: (params?: { next?: string; previous?: string }) => Promise<void>;
  setBlueprints: (blueprints: Blueprint[], paging: Paging) => void;
  setSearchTerm: (term: string | null) => void;
  fetchTagDescriptions: () => Promise<void>;
  setInitialSetupComplete: (complete: boolean) => void;
}

export const createTagStore = (autoload = false, search_models = false, search_blueprints = false) => {
  return createStore<TagStore>((set, get) => ({
    data: {},
    expandedNodes: {},
    selectedTags: [],
    denyTags: [],
    blueprints: [],
    paging: null,
    autoload,
    search_models,
    search_blueprints,
    searchTerm: null,
    tagDescriptions: {},
    initialSetupComplete: false,
    fetchData: async () => {
      const { search_models, search_blueprints, selectedTags, denyTags } = get();
      const params = new URLSearchParams();

      // Add parameters for model/blueprint search
      params.set('models', String(search_models));
      params.set('blueprints', String(search_blueprints));

      const requestBody = {
        require: selectedTags.map(tag => ({ tag })),
        deny: denyTags.map(tag => ({ tag })),
      };

      const response = await fetch(`/api/blueprints/tags${params.toString() ? '?' + params.toString() : ''}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(requestBody),
      });
      const result = await response.json();
      const tagCounts = result.tag_counts;
      devLog('Fetched tag data:', tagCounts);
      get().setData(tagCounts);
    },
    setData: (tagCounts: Record<string, number>) => {
      devLog('setData', tagCounts);
      const data: Record<string, TagNode> = {};

      Object.entries(tagCounts).forEach(([key, count]) => {
        const tags = key.split('|');
        let currentLevel = data;
        let fullPath = '';

        tags.forEach((tag, index) => {
          if (fullPath) {
            fullPath += `|${tag}`;
          } else {
            fullPath = tag;
          }

          if (!currentLevel[tag]) {
            currentLevel[tag] = { children: {}, __name: fullPath };
          }

          if (index === tags.length - 1) {
            currentLevel[tag].__count = count as number;
          } else {
            currentLevel = currentLevel[tag].children!;
          }
        });
      });

      // Aggregate counts for non-leaf nodes
      const aggregateCounts = (node: TagNode) => {
        if (!node) return 0;
        let total = node.__count || 0;
        let subTags = 0;
        Object.values(node.children || {}).forEach((child) => {
          if (typeof child === 'object') {
            subTags++;
            total += aggregateCounts(child);
          }
        });
        node.__totalCount = total;
        node.__subTags = subTags;
        return total;
      };

      Object.values(data).forEach((node) => {
        if (typeof node === 'object') {
          aggregateCounts(node);
        }
      });

      set({ data });
    },
    toggleNode: (key: string) => {
      devLog('toggleNode', key);
      set((state) => ({
        expandedNodes: {
          ...state.expandedNodes,
          [key]: !state.expandedNodes[key],
        },
      }));
    },
    addTag: (tag: string) => {
      devLog('addTag', tag);
      set((state) => {
        const newDenyTags = state.denyTags.filter((t) => t !== tag);
        const newSelectedTags = state.selectedTags.includes(tag)
          ? state.selectedTags
          : [...state.selectedTags, tag];

        // Only update state if there's a change to avoid unnecessary re-renders
        if (newDenyTags.length === state.denyTags.length && newSelectedTags.length === state.selectedTags.length) {
          return state;
        }

        return {
          selectedTags: newSelectedTags,
          denyTags: newDenyTags,
        };
      });
      get().fetchBlueprints();
    },
    addAllTags: (tags: string[]) => {
      devLog('addAllTags', tags);
      set((state) => {
        const uniqueTags = Array.from(new Set([...state.selectedTags, ...tags]));
        return { selectedTags: uniqueTags };
      });
      get().fetchBlueprints();
    },
    removeTag: (tag: string) => {
      devLog('removeTag', tag);
      set((state) => {
        const updatedSelectedTags = state.selectedTags.filter((t) => t !== tag);
        const updatedDenyTags = state.denyTags.filter((t) => t !== tag);

        // Only update state if there's a change to avoid unnecessary re-renders
        if (updatedSelectedTags.length === state.selectedTags.length && updatedDenyTags.length === state.denyTags.length) {
          return state;
        }

        return { selectedTags: updatedSelectedTags, denyTags: updatedDenyTags };
      });
      get().fetchBlueprints();
    },
    addDenyTag: (tag: string) => {
      devLog('addDenyTag', tag);
      set((state) => {
        const newSelectedTags = state.selectedTags.filter((t) => t !== tag);
        const newDenyTags = state.denyTags.includes(tag)
          ? state.denyTags
          : [...state.denyTags, tag];

        // Only update state if there's a change to avoid unnecessary re-renders
        if (newSelectedTags.length === state.selectedTags.length && newDenyTags.length === state.denyTags.length) {
          return state;
        }

        return {
          selectedTags: newSelectedTags,
          denyTags: newDenyTags,
        };
      });
      get().fetchBlueprints();
    },
    removeDenyTag: (tag: string) => {
      devLog('removeDenyTag', tag);
      set((state) => {
        const updatedTags = state.denyTags.filter((t) => t !== tag);
        return { denyTags: updatedTags };
      });
      get().fetchBlueprints();
    },
    clearTags: () => {
      devLog('clearTags');
      set({ selectedTags: [], denyTags: [], searchTerm: null });
      // Clear blueprint selection by setting it to null
      const blueprintStore = (window as { __BLUEPRINT_STORE__?: { getState: () => { setSelectedBlueprint: (blueprint: Blueprint | null) => void } } }).__BLUEPRINT_STORE__;
      if (blueprintStore) {
        blueprintStore.getState().setSelectedBlueprint(null);
      }
      get().fetchBlueprints();
    },
    setTagState: (tags: { require?: string[]; deny?: string[]; searchTerm?: string | null }) => {
      devLog('setTagState', tags);
      const updates: Partial<Pick<TagStore, 'selectedTags' | 'denyTags' | 'searchTerm'>> = {
        selectedTags: tags.require || [],
        denyTags: tags.deny || [],
      };
      if ('searchTerm' in tags) {
        updates.searchTerm = tags.searchTerm;
      }
      set(updates);
      get().fetchBlueprints();
    },
    setSearchTerm: (term: string | null) => {
      devLog('setSearchTerm', term);
      set({ searchTerm: term });
      get().fetchBlueprints();
    },
    fetchBlueprints: async (params?: { next?: string; previous?: string }) => {
      const { selectedTags, denyTags, search_models, search_blueprints, searchTerm } = get();

      const urlParams = new URLSearchParams();

      // Add search type parameters
      urlParams.set('models', String(search_models));
      urlParams.set('blueprints', String(search_blueprints));

      // Add search parameter if present
      if (searchTerm) {
        urlParams.set('search', searchTerm);
      }

      // Add pagination parameters if provided
      if (params?.next) {
        urlParams.set('next', params.next);
      } else if (params?.previous) {
        urlParams.set('previous', params.previous);
      }

      const requestBody = {
        require: selectedTags.map(tag => ({ tag })),
        deny: denyTags.map(tag => ({ tag })),
      };

      const response = await fetch(`/api/blueprints/tags${urlParams.toString() ? '?' + urlParams.toString() : ''}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(requestBody),
      });
      const result = await response.json();
      devLog('Fetched blueprints:', result);
      get().setBlueprints(result.blueprints, result.paging);
      get().setData(result.tag_counts);
    },
    setBlueprints: (blueprints, paging) => {
      set({ blueprints, paging });
    },
    fetchTagDescriptions: async () => {
      const response = await fetch('/api/tag-descriptions');
      const descriptions = await response.json();
      set({ tagDescriptions: descriptions });
    },
    setInitialSetupComplete: (complete: boolean) => {
      set({ initialSetupComplete: complete });
    },
  }));
};
