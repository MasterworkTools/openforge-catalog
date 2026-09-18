import { useEffect, useRef } from 'react';
import { useBlueprintContext } from '@/contexts/blueprint-context';
import { useTagContext } from '@/contexts/tag-context';

/**
 * Custom hook to handle URL parameters for autoloading tags, search terms, and blueprint selection
 */
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

      // Remove tag parameters from URL after processing
      const newParams = new URLSearchParams();
      if (blueprintId) {
        newParams.set('blueprint_id', blueprintId);
      }
      const newUrl = `${window.location.pathname}${newParams.toString() ? '?' + newParams.toString() : ''}`;

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
