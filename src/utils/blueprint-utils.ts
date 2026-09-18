import { Blueprint, ConfigPart } from '@/types';

/**
 * Navigate to a URL (default implementation)
 * @param url - The URL to navigate to
 */
export const navigate = (url: string) => {
  window.location.href = url;
};

/**
 * Download multiple files sequentially
 * @param urls - Array of download URLs
 * @param nav - Navigation function (defaults to window.location.href)
 */
export const downloadFiles = async (urls: string[], nav: (url: string) => void = navigate) => {
  if (urls.length === 0) return;

  if (urls.length === 1) {
    nav(urls[0]);
    return;
  }

  // For multiple files, download sequentially with delay
  const downloadWithDelay = async (url: string, index: number) => {
    return new Promise<void>((resolve) => {
      setTimeout(async () => {
        const iframe = document.createElement('iframe');
        iframe.style.display = 'none';
        iframe.src = url;
        document.body.appendChild(iframe);

        // Remove iframe after a delay to ensure download starts
        setTimeout(() => {
          document.body.removeChild(iframe);
          resolve();
        }, 1000);
      }, index * 1000); // 1 second delay between downloads
    });
  };

  // Download files sequentially
  for (let i = 0; i < urls.length; i++) {
    await downloadWithDelay(urls[i], i);
  }
};

/**
 * Determines if a download link should be shown for a blueprint
 * @param blueprint - The blueprint to check
 * @param configSelections - Current configuration selections
 * @returns True if download link should be shown
 */
export function shouldShowDownloadLink(
  blueprint: Blueprint,
  configSelections: Record<string, Blueprint>
): boolean {
  if (blueprint.file_name) {
    return true;
  }

  if (blueprint.blueprint_config?.parts) {
    const requiredParts = blueprint.blueprint_config.parts.filter(part =>
      !part.optional && part.tags.require && part.tags.require.length > 0
    );

    return requiredParts.every(part =>
      checkPartRequirements(part, configSelections, part.name)
    );
  }

  return false;
}

/**
 * Recursively checks if all required parts in a nested hierarchy are selected
 * @param part - The part to check
 * @param configSelections - Current configuration selections
 * @param currentPath - The current path in the hierarchy (e.g., "parent|child")
 * @returns True if all required parts are selected
 */
function checkPartRequirements(
  part: ConfigPart,
  configSelections: Record<string, Blueprint>,
  currentPath: string
): boolean {
  const selectedBlueprint = configSelections[currentPath];
  if (!selectedBlueprint) return false;

  // Check if the selected blueprint has its own required parts
  if (selectedBlueprint.blueprint_config?.parts) {
    const nestedRequiredParts = selectedBlueprint.blueprint_config.parts.filter(nestedPart =>
      !nestedPart.optional && nestedPart.tags.require && nestedPart.tags.require.length > 0
    );
    return nestedRequiredParts.every(nestedPart =>
      checkPartRequirements(nestedPart, configSelections, `${currentPath}|${nestedPart.name}`)
    );
  }

  return true;
}

/**
 * Collects all download URLs for a blueprint and its selected parts
 * @param blueprint - The main blueprint
 * @param configSelections - Current configuration selections
 * @returns Array of download URLs
 */
export function collectDownloadUrls(
  blueprint: Blueprint,
  configSelections: Record<string, Blueprint>
): string[] {
  const urls: string[] = [];
  const processedBlueprints = new Set<string>();

  // Add main blueprint download if it has a file_name
  if (blueprint.file_name) {
    urls.push(`/api/blueprints/${blueprint.id}/download`);
    processedBlueprints.add(blueprint.id);
  }

  // Add downloads for each selected part and its nested parts
  const processBlueprint = (bp: Blueprint) => {
    if (bp.file_name && !processedBlueprints.has(bp.id)) {
      urls.push(`/api/blueprints/${bp.id}/download`);
      processedBlueprints.add(bp.id);
    }
  };

  // Process all selected blueprints
  Object.entries(configSelections).forEach(([, bp]) => {
    processBlueprint(bp);
  });

  return urls;
}

/**
 * Gets the latest modification date from a blueprint
 * @param blueprint - The blueprint to check
 * @returns The latest date as a Date object
 */
export function getLatestModificationDate(blueprint: Blueprint): Date {
  return new Date(blueprint.file_modified_at);
}
