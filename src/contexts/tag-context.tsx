'use client'

import React, { createContext, useContext, useMemo } from 'react';
import { StoreApi, useStore } from 'zustand';
import { createTagStore, TagStore } from '@/stores/tag-store';

type TagContext = StoreApi<TagStore> | null;

const TagContext = createContext<TagContext>(null);

export function TagProvider({
  children,
  autoload = false,
  search_models = true,
  search_blueprints = false
}: {
  children: React.ReactNode;
  autoload?: boolean;
  search_models?: boolean;
  search_blueprints?: boolean;
}) {
  // IMPORTANT: Empty dependency array is intentional!
  // Zustand stores must be created ONCE and never recreated. The props (autoload, search_models, search_blueprints)
  // are initial configuration values used at creation time. Recreating the store would lose all state
  // (selectedTags, blueprints, paging, etc.) and cause infinite re-render loops.
  // See: https://github.com/pmndrs/zustand/discussions/1937
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const store = useMemo(() => createTagStore(autoload, search_models, search_blueprints), []);

  return (
    <TagContext.Provider value={store}>
      {children}
    </TagContext.Provider>
  );
}

export function useTagContext<T>(selector: (state: TagStore) => T) {
  const store = useContext(TagContext);
  if (!store) {
    throw new Error('useTagContext must be used within a TagProvider');
  }
  return useStore(store, selector);
}
