import { useEffect, useRef } from 'react';
import { useBlueprintContext } from '@/contexts/blueprint-context';
import { useTagContext } from '@/contexts/tag-context';

/**
 * Custom hook to handle URL parameters for autoloading tags, search terms, and blueprint selection
 */
/**
 * The query-string parameters `useUrlParameters` consumes and removes.
 *
 * Everything else on the URL belongs to somebody else and survives.
 */
export const CONSUMED = ['tag', 'deny', 'search', 'blueprint_id'] as const;

/**
 * The query string with this hook's own parameters taken out.
 *
 * Exported and pure so it can be checked directly: the suite for this
 * hook mocks `URLSearchParams` globally, so a test written there proves
 * things about the mock rather than about the URL.
 *
 * It used to build the result from empty and re-add only
 * `blueprint_id`, which ate every other parameter. Invisible while `/`
 * had nothing else in its query string — then the Guided Builds tab
 * arrived, and `/?guide=wall` was stripped to `/` on load by this hook,
 * which lives inside the permanently-mounted Part Search tab. A shared
 * guide link opened Part Search with no guide.
 */
export function withoutConsumed(search: string, blueprintId?: string | null): string {
  const kept = new URLSearchParams(search);
  for (const name of CONSUMED) kept.delete(name);
  if (blueprintId) kept.set('blueprint_id', blueprintId);
  return kept.toString();
}

export function useUrlParameters() {
  const setSelectedBlueprint = useBlueprintContext((state) => state.setSelectedBlueprint);
  const blueprints = useTagContext((state) => state.blueprints);
  const setTagState = useTagContext((state) => state.setTagState);
  const setInitialSetupComplete = useTagContext((state) => state.setInitialSetupComplete);
  const autoload = useTagContext((state) => state.autoload);
  const hasSetTagState = useRef<boolean>(false);

  useEffect(() => {
    // If not autoloading, mark setup as complete immediately
    if (!autoload) {
      setInitialSetupComplete(true);
      return;
    }

    // Read URL parameters and add tags
    if (typeof window !== 'undefined' && !hasSetTagState.current) {
      const params = new URLSearchParams(window.location.search);

      // Handle tags - collect all tags to add at once
      const tagParams = params.getAll('tag');

      // Handle deny tags
      const denyParams = params.getAll('deny');

      // Handle search term
      const searchParam = params.get('search');

      // Mark that we've processed URL parameters
      hasSetTagState.current = true;

      // Set all state at once to trigger only one fetchBlueprints call
      setTagState({
        require: tagParams,
        deny: denyParams,
        searchTerm: searchParam
      });

      // Handle blueprint selection
      const blueprintId = params.get('blueprint_id');
      if (blueprintId) {
        const blueprint = blueprints.find(b => b.id === blueprintId);
        if (blueprint) {
          setSelectedBlueprint(blueprint);
        }
      }

      // Drop the parameters this hook just consumed, and keep the rest.
      //
      // This used to build the query from empty and re-add only
      // `blueprint_id`, which silently ate every other parameter on the
      // page. That was invisible while `/` had nothing else in its
      // query string — and then the Guided Builds tab arrived, and
      // `/?guide=wall` was stripped to `/` on load by a hook inside the
      // *Part Search* tab, which is mounted permanently. A shared guide
      // link opened Part Search with no guide.
      //
      // Deleting what it read, rather than whitelisting what it keeps,
      // is also the version that does not break the next parameter
      // somebody adds. `guide` and a guide's answers survive; the four
      // this hook consumes do not.
      const kept = withoutConsumed(window.location.search, blueprintId);
      const newUrl = `${window.location.pathname}${kept ? '?' + kept : ''}`;

      // Only update URL if it actually changed
      if (newUrl !== window.location.href) {
        window.history.replaceState({}, '', newUrl);
      }

      // Mark initial setup as complete
      setInitialSetupComplete(true);
    }
  }, [autoload, setTagState, blueprints, setSelectedBlueprint, setInitialSetupComplete]);

  return { hasSetTagState };
}
