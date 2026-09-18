'use client'

import React, { useEffect, useRef } from 'react';
import { useBlueprintContext } from '@/contexts/blueprint-context';
import { useTagContext } from '@/contexts/tag-context';
import { Blueprint, ConfigTags } from '@/types';
import { processConfigValues, createDeepLink } from '@/utils/config-processing';
import { useUrlParameters } from '@/hooks/use-url-parameters';
import { useCopyToClipboard } from '@/hooks/use-copy-to-clipboard';
import { PaginationControls } from '@/components/ui/pagination-controls';
import { SelectedTagsDisplay } from '@/components/results/selected-tags-display';
import { BlueprintList } from '@/components/results/blueprint-list';
import './results-container.css';

interface ResultsContainerProps {
  configValues?: ConfigTags | null;
  parentTags?: string[];
  siblingSelections?: { partName: string; tags: string[] }[];
}

const ResultsContainer = ({ configValues, parentTags = [], siblingSelections = [] }: ResultsContainerProps) => {
  const setSelectedBlueprint = useBlueprintContext((state) => state.setSelectedBlueprint);
  const selectedBlueprint = useBlueprintContext((state) => state.selectedBlueprint);
  const blueprints = useTagContext((state) => state.blueprints);
  const paging = useTagContext((state) => state.paging);
  const selectedTags = useTagContext((state) => state.selectedTags);
  const denyTags = useTagContext((state) => state.denyTags);
  const searchTerm = useTagContext((state) => state.searchTerm);
  const removeTag = useTagContext((state) => state.removeTag);
  const clearTags = useTagContext((state) => state.clearTags);
  const fetchBlueprints = useTagContext((state) => state.fetchBlueprints);
  const setTagState = useTagContext((state) => state.setTagState);
  const fetchData = useTagContext((state) => state.fetchData);
  const setSearchTerm = useTagContext((state) => state.setSearchTerm);
  const { copied, copyText } = useCopyToClipboard();

  const { hasSetTagState } = useUrlParameters();
  const lastProcessedConfig = useRef<string>('');
  const setupInProgress = useRef<boolean>(false);

  // Helper function to compare tag arrays for equality
  const areTagArraysUnsortedEqual = (a: string[], b: string[]): boolean => {
    if (a.length !== b.length) return false;
    // Create copies before sorting to avoid mutating original arrays
    const sortedA = [...a].sort();
    const sortedB = [...b].sort();
    return sortedA.every((value, index) => value === sortedB[index]);
  };

  useEffect(() => {
    if (configValues) {
      // Create a hash of the current config to prevent unnecessary updates
      const configHash = JSON.stringify({ configValues, parentTags, siblingSelections });
      if (configHash === lastProcessedConfig.current && !setupInProgress.current) {
        return; // Skip if config hasn't actually changed and we're not in setup
      }

      // Only update lastProcessedConfig if we're actually going to process this config
      const isNewConfig = configHash !== lastProcessedConfig.current;
      if (isNewConfig) {
        lastProcessedConfig.current = configHash;
      }

      let isCancelled = false;

      const derivedTags = processConfigValues(configValues, parentTags, siblingSelections);

      const setTags = () => {
        if (!isCancelled) {
          setTagState(derivedTags);
          // eslint-disable-next-line react-hooks/immutability
          hasSetTagState.current = true;

          setupInProgress.current = false;
        }
      };

      if (!hasSetTagState.current) {
        // Initial setup

        setupInProgress.current = true;
        if (fetchData) {
          const result = fetchData();
          if (result && typeof result.then === 'function') {
            result.then(setTags);
          } else {
            setTags();
          }
        } else {
          setTags();
        }
      } else {
        // Handle updates to props after initial setup
        // Preserve user-added tags while updating derived ones
        const userAddedTags = selectedTags.filter(tag =>
          !derivedTags.require?.includes(tag) &&
          !derivedTags.deny?.includes(tag)
        );

        // Ensure we always work with arrays, even if derivedTags properties are undefined/null
        const derivedRequire = Array.isArray(derivedTags.require) ? derivedTags.require : [];
        const derivedDeny = Array.isArray(derivedTags.deny) ? derivedTags.deny : [];

        const mergedTags = {
          require: [...derivedRequire, ...userAddedTags],
          deny: derivedDeny
        };

        // Compare arrays to prevent infinite loops
        const requireChanged = !areTagArraysUnsortedEqual(mergedTags.require || [], selectedTags);
        const denyChanged = !areTagArraysUnsortedEqual(mergedTags.deny || [], denyTags);

        if (requireChanged || denyChanged) {
          setTagState(mergedTags);
        }
      }

      return () => {
        isCancelled = true;
      };
    }
  }, [configValues, parentTags, siblingSelections, fetchData, setTagState, hasSetTagState, selectedTags, denyTags]);

  const handleSelect = (blueprint: Blueprint) => {
    setSelectedBlueprint(blueprint);
  };

  const handleRemoveTag = (tag: string) => {
    removeTag(tag);
  };

  const isTagRemovable = (tag: string): boolean => {
    // Tag is not removable if it's from other selections
    if (parentTags.includes(tag) || siblingSelections.some(selection => selection.tags.includes(tag))) {
      return false;
    }
    // If configValues exists, check if the tag is in require or deny
    if (configValues) {
      // Check require section
      if (configValues.require) {
        for (const data of configValues.require) {
          if (data.tag === tag) {
            return false;
          }
        }
      }
      // Check deny section
      if (configValues.deny) {
        for (const data of configValues.deny) {
          if (data.tag === tag) {
            return false;
          }
        }
      }
    }
    return true;
  };

  const handleClear = (e: React.MouseEvent) => {
    e.preventDefault();
    clearTags();
    setSelectedBlueprint(null);
  };

  const startCount = (paging?.start_count ?? 0) + 1;
  const endCount = startCount + blueprints.length - 1;

  const handleCopyToClipboard = (text: string) => {
    const currentUrl = window.location.href;
    const urlWithoutParameters = currentUrl.split("?")[0];
    const textToCopy = urlWithoutParameters + '?' + text;
    copyText(textToCopy);
  };

  return (
    <div className='resultsContainer'>
      <h2>Blueprints</h2>
      {(selectedTags.length > 0 || denyTags.length > 0 || searchTerm) && (
        <>
          <SelectedTagsDisplay
            selectedTags={selectedTags}
            denyTags={denyTags}
            searchTerm={searchTerm}
            configValues={configValues}
            isTagRemovable={isTagRemovable}
            onRemoveTag={handleRemoveTag}
            onClearSearch={() => setSearchTerm(null)}
            onCreateDeepLink={() => createDeepLink(selectedTags, searchTerm, denyTags)}
            onCopyToClipboard={handleCopyToClipboard}
            copied={copied}
          />
          {!configValues && <div className='selectedTagsContainer__header'><a className='visibleLink' href="#" onClick={handleClear}>clear</a></div>}
        </>
      )}

      <BlueprintList
        blueprints={blueprints}
        selectedBlueprint={selectedBlueprint}
        onSelectBlueprint={handleSelect}
      />

      <PaginationControls
        paging={paging}
        startCount={startCount}
        endCount={endCount}
        totalCount={paging?.total_count ?? 0}
        onPrevious={() => fetchBlueprints({ previous: paging?.previous_token })}
        onNext={() => fetchBlueprints({ next: paging?.next_token })}
      />
    </div>
  );
};

export default ResultsContainer;
