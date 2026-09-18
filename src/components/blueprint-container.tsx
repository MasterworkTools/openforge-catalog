'use client'

import React, { useMemo } from 'react';
import { Blueprint } from '@/types';
import { useBlueprintContext } from '@/contexts/blueprint-context';
import { useTagContext } from '@/contexts/tag-context';
import { formatFileSize } from '@/utils/format';
import { shouldShowDownloadLink, collectDownloadUrls, getLatestModificationDate, downloadFiles } from '@/utils/blueprint-utils';
import { buildNestedConfigs } from '@/utils/config-processing';
import { swapTagsByType } from '@/utils/tag-utils';
import { useBlueprintUrlCleanup } from '@/hooks/use-blueprint-url-cleanup';
import { useCopyToClipboard } from '@/hooks/use-copy-to-clipboard';
import newGithubIssueUrl from 'new-github-issue-url';
import TagRow from './ui/tag-row';
import ConfigSection from './blueprint/config-section';
import ImageGallery from './blueprint/image-gallery';
import BlueprintHeader from './blueprint/blueprint-header';
import BlueprintMeta from './blueprint/blueprint-meta';
import BlueprintRelatedLinks from './blueprint/blueprint-related-links';
import BlueprintActions from './blueprint/blueprint-actions';
import BlueprintDetailsTabs from './blueprint-details-tabs';
import './blueprint-container.css';

interface BlueprintContainerProps {
  configValues?: { partName: string } | null;
  onPartSelected?: (partName: string, blueprint: Blueprint) => void;
}

const BlueprintContainer = ({ configValues, onPartSelected }: BlueprintContainerProps) => {
  const blueprint = useBlueprintContext((state) => state.selectedBlueprint);
  const configSelections = useBlueprintContext((state) => state.configSelections);
  const addTag = useTagContext((state) => state.addTag);
  const clearTags = useTagContext((state) => state.clearTags);
  const addAllTags = useTagContext((state) => state.addAllTags);
  const { copied, copyText } = useCopyToClipboard();

  // Use custom hook for URL cleanup
  useBlueprintUrlCleanup(blueprint);

  // Derive nested configs from configSelections
  const nestedConfigs = useMemo(() => buildNestedConfigs(configSelections), [configSelections]);

  const handleDownload = (e: React.MouseEvent) => {
    e.preventDefault();
    if (!blueprint) return;

    const urls = collectDownloadUrls(blueprint, configSelections);
    downloadFiles(urls);
  };

  const handleCopyToClipboard = (blueprint_md5: string) => {
    const currentUrl = window.location.href;
    const baseUrl = currentUrl.split("?")[0];
    const textToCopy = baseUrl + '?md5=' + blueprint_md5;
    copyText(textToCopy);
  };

  const handleSwapTags = (e: React.MouseEvent, blueprint: Blueprint, tagType: string) => {
    e.preventDefault();
    const newTags = swapTagsByType(blueprint, tagType);
    clearTags();
    addAllTags(newTags);
  };

  if (!blueprint) {
    return <div>No Blueprint Selected</div>;
  }

  const issue_url = newGithubIssueUrl({
    user: 'devonjones',
    repo: 'openforge_catalog',
    body: 'Model Reported: ' + window.location + '\n---\n\n\n'
  });

  const laterDate = getLatestModificationDate(blueprint);
  const currentPath = window.location.pathname;
  const deeplink = `${currentPath}?md5=${blueprint.file_md5}`;

  return (
    <BlueprintDetailsTabs blueprint={blueprint}>
      <BlueprintHeader
        name={blueprint.blueprint_name}
        fullName={blueprint.full_name}
        deeplink={deeplink}
        copied={copied}
        onCopy={() => handleCopyToClipboard(blueprint.file_md5)}
        showDeeplink={!configValues}
      />
      <BlueprintMeta
        type={blueprint.blueprint_type}
        lastModified={laterDate.toLocaleString()}
        size={formatFileSize(blueprint.file_size)}
      />
      <TagRow
        tags={blueprint.tags}
        onTagClick={addTag}
      />
      {!configValues && (
        <BlueprintRelatedLinks onSwap={(e, tagType) => handleSwapTags(e, blueprint, tagType)} />
      )}
      <BlueprintActions
        configValues={configValues}
        onSelectPart={configValues && onPartSelected ? () => onPartSelected(configValues.partName, blueprint) : null}
        showDownload={shouldShowDownloadLink(blueprint, configSelections) && !configValues}
        onDownload={handleDownload}
        issueUrl={issue_url}
      />
      <ConfigSection
        blueprint={blueprint}
        nestedConfigs={nestedConfigs}
        configValues={configValues}
      />
      <ImageGallery blueprint={blueprint} />
    </BlueprintDetailsTabs>
  );
};

export default BlueprintContainer;
