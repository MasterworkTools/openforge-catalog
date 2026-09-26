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
  /**
   * A blueprint to open on, by md5.
   *
   * For a caller that already knows which piece it is talking about —
   * the guide opens the catalog on the part you clicked, rather than
   * on "No Blueprint Selected" beside a list you have to search for
   * something you were already looking at.
   *
   * Separate from `autoload`, which reads the *page's* query string.
   * A modal has no URL of its own, and giving it one would fight the
   * page it opened over.
   */
  initialMd5?: string | null;
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

export function BlueprintProvider({ children, autoload = false, initialMd5 = null }: BlueprintProviderProps) {
  // IMPORTANT: Empty dependency array is intentional!
  // Zustand stores must be created ONCE and never recreated. Recreating the store
  // would lose all state and cause infinite re-render loops.
  const store = useMemo(() => createBlueprintStore(), []);

  useEffect(() => {
    if (!initialMd5) return;
    let current = true;
    store.getState().fetchBlueprintByMd5(initialMd5)
      .then(blueprint => {
        // Not if the caller has moved on. Opening on a piece is a
        // convenience; landing on it after the person has clicked
        // something else would be the opposite of one.
        if (current) store.getState().setSelectedBlueprint(blueprint);
      })
      .catch(error => {
        // The list is still there to search. A part whose file has
        // been replaced since the link was made is a reason to open
        // on nothing, not to break the dialog.
        console.error('Failed to open on blueprint:', error);
      });
    return () => { current = false; };
  }, [initialMd5, store]);

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
