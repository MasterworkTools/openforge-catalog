import { useEffect } from 'react';
import { Blueprint } from '@/types';

/**
 * Custom hook to handle blueprint URL cleanup and browser navigation
 * @param blueprint - The current blueprint or null
 * @param location - Optional location object (defaults to window.location if available)
 * @param history - Optional history object (defaults to window.history if available)
 */
export function useBlueprintUrlCleanup(
  blueprint: Blueprint | null,
  location?: Location,
  history?: History
) {
  useEffect(() => {
    // Only run on client side
    if (typeof window === 'undefined') return;

    const currentLocation = location || window.location;
    const currentHistory = history || window.history;

    // Handle URL cleanup and browser navigation
    if (blueprint) {
      // Remove blueprint_id from URL after it's been used
      const params = new URLSearchParams(currentLocation.search);
      if (params.has('blueprint_id')) {
        params.delete('blueprint_id');
        const newUrl = currentLocation.pathname + (params.toString() ? '?' + params.toString() : '');
        currentHistory.replaceState({}, '', newUrl);
      }
    }

    // Handle browser back/forward buttons
    const handlePopState = () => {
      const params = new URLSearchParams(currentLocation.search);
      const blueprintId = params.get('blueprint_id');
      if (!blueprintId && blueprint) {
        currentLocation.reload();
      }
    };

    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
  }, [blueprint, location, history]);
}
