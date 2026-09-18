'use client'

import React, { createContext, useContext, useEffect, Suspense, useMemo } from 'react';
import { StoreApi, useStore } from 'zustand';
import { createBlueprintStore, BlueprintStore } from '@/stores/blueprint-store';
import { useSearchParams } from 'next/navigation';

type BlueprintContext = StoreApi<BlueprintStore> | null;

export const BlueprintContext = createContext<BlueprintContext>(null);

interface BlueprintProviderProps {
  children: React.ReactNode;
  autoload?: boolean;
}

interface BlueprintProviderInnerProps extends BlueprintProviderProps {
  store: StoreApi<BlueprintStore>;
}

function BlueprintProviderInner({ children, autoload = false, store }: BlueprintProviderInnerProps) {
  const searchParams = useSearchParams();
  const blueprintId = autoload ? searchParams.get('blueprint_id') : null;
  const md5 = autoload ? searchParams.get('md5') : null;

  useEffect(() => {
    if (blueprintId) {
      store.getState().fetchBlueprintById(blueprintId)
        .then(blueprint => {
          store.getState().setSelectedBlueprint(blueprint);
        })
        .catch(error => {
          console.error('Failed to fetch initial blueprint:', error);
        });
    } else if (md5) {
      store.getState().fetchBlueprintByMd5(md5)
        .then(blueprint => {
          store.getState().setSelectedBlueprint(blueprint);
        })
        .catch(error => {
          console.error('Failed to fetch initial blueprint:', error);
        });
    }
  }, [blueprintId, md5, store]);

  return (
    <BlueprintContext.Provider value={store}>
      {children}
    </BlueprintContext.Provider>
  );
}

export function BlueprintProvider({ children, autoload = false }: BlueprintProviderProps) {
  // IMPORTANT: Empty dependency array is intentional!
  // Zustand stores must be created ONCE and never recreated. Recreating the store
  // would lose all state and cause infinite re-render loops.
  const store = useMemo(() => createBlueprintStore(), []);

  if (autoload) {
    return (
      <Suspense fallback={
        <BlueprintContext.Provider value={store}>
          {children}
        </BlueprintContext.Provider>
      }>
        <BlueprintProviderInner autoload={autoload} store={store}>
          {children}
        </BlueprintProviderInner>
      </Suspense>
    );
  }

  return (
    <BlueprintContext.Provider value={store}>
      {children}
    </BlueprintContext.Provider>
  );
}

export function useBlueprintContext<T>(selector: (state: BlueprintStore) => T) {
  const store = useContext(BlueprintContext);
  if (!store) {
    throw new Error('useBlueprintContext must be used within a BlueprintProvider');
  }
  return useStore(store, selector);
}
