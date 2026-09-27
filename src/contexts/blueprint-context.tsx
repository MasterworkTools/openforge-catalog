'use client'

import React, { createContext, useContext, useEffect, useMemo, useRef, Suspense } from 'react';
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

  // The md5 this effect last put in the store, so a piece the person
  // chose can be told from one we seeded.
  const seeded = useRef<string | null>(null);

  useEffect(() => {
    if (!initialMd5) return;
    let current = true;
    store.getState().fetchBlueprintByMd5(initialMd5)
      .then(blueprint => {
        // Only if nothing has been selected since. The cleanup alone
        // does not cover this: it runs when `initialMd5` changes or
        // the provider unmounts, and clicking a different result does
        // neither — so a slow fetch used to land on top of the piece
        // the person had just chosen. Reading the store is what
        // actually answers "have they moved on".
        //
        // Against what *this effect* last seeded, not against "is
        // anything selected". The latter is permanently true after
        // the first open, so it would make the effect ignore the very
        // prop it depends on; and a bare md5 comparison cannot tell a
        // piece the person clicked from the one the previous md5
        // seeded, because neither matches the md5 now being asked
        // for. Remembering what we put there separates the two.
        const selected = store.getState().selectedBlueprint;
        const ours = !selected || selected.file_md5 === seeded.current;
        if (!current || !ours) return;
        seeded.current = initialMd5;
        store.getState().setSelectedBlueprint(blueprint);
      })
      .catch(error => {
        // Only the fetch. The list is still there to search, and a
        // part whose file has been replaced since the link was made
        // is a reason to open on nothing rather than to break the
        // dialog. A failure inside `setSelectedBlueprint` is not that
        // and must not be filed under it, hence the md5 in the
        // message and the `.then` doing no work that can throw.
        console.error(`Failed to open on blueprint ${initialMd5}:`, error);
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
