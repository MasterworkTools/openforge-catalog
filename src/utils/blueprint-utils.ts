import { Blueprint, ConfigPart } from '@/types';

/**
 * Navigate to a URL (default implementation)
 * @param url - The URL to navigate to
 */
export const navigate = (url: string) => {
  window.location.href = url;
};

/**
 * How long a download iframe stays in the DOM.
 *
 * Was 1000 ms, and that was a race the browser lost. Removing an iframe whose
 * request has not started transferring aborts it — `NS_BINDING_ABORTED` in
 * Firefox — and `/api/blueprints/<id>/download` only 302s to a presigned R2
 * URL, after which the browser still has to open a connection to R2 and begin
 * the transfer. Measured on production: that redirect takes 5.03 s on a cold
 * Lambda and 0.35 s warm, so a cold start missed the old budget every time and
 * a warm one missed it for anyone far from us-east or on cellular
 * (openforge_catalog-m8i, reported from New Zealand).
 *
 * A minute is not a considered number; it is "longer than any download takes to
 * *start*". The iframes cost nothing while they sit there, and the reason to
 * remove them at all is tidiness rather than correctness.
 */
const DOWNLOAD_IFRAME_LIFETIME_MS = 60_000;

/** What `downloadFiles` managed to do, so a caller can say so. */
export interface DownloadOutcome {
  /** URLs whose download was handed to the browser. */
  started: string[];
  /** URLs that could not be presigned; nothing was handed to the browser. */
  failed: string[];
}

/**
 * Download one or many files.
 *
 * One file is a plain navigation: the response is an attachment, so the browser
 * downloads it and stays put, and there is nothing to race.
 *
 * Many files cannot each be a navigation, so each gets a hidden iframe. Before
 * creating one, the redirect is asked for with `redirect: 'manual'`, which stops
 * at the 302 without following it: that costs one presign and no file transfer,
 * tells us whether the file can be fetched at all, and leaves the container warm
 * for the iframe that immediately follows — which is what takes the cold start
 * out of the download's critical path.
 *
 * Awaiting each probe also paces the iframes, so no artificial stagger is needed.
 */
export const downloadFiles = async (
  urls: string[],
  nav: (url: string) => void = navigate
): Promise<DownloadOutcome> => {
  if (urls.length === 0) return { started: [], failed: [] };

  if (urls.length === 1) {
    nav(urls[0]);
    return { started: [urls[0]], failed: [] };
  }

  const started: string[] = [];
  const failed: string[] = [];

  for (const url of urls) {
    let presigned = false;
    try {
      const probe = await fetch(url, { redirect: 'manual' });
      // A followed-but-not-followed redirect comes back opaque: no status, no
      // headers. That is the success case here — the server had something to
      // redirect us to. A real status means it answered instead of redirecting,
      // which is only good if it is a 2xx.
      presigned = probe.type === 'opaqueredirect' || probe.ok;
    } catch {
      presigned = false;
    }

    if (!presigned) {
      failed.push(url);
      continue;
    }

    const iframe = document.createElement('iframe');
    iframe.style.display = 'none';
    iframe.src = url;
    document.body.appendChild(iframe);
    started.push(url);

    setTimeout(() => {
      if (iframe.parentNode) document.body.removeChild(iframe);
    }, DOWNLOAD_IFRAME_LIFETIME_MS);
  }

  if (failed.length > 0) {
    // console, not the page: src/CLAUDE.md puts frontend error handling at
    // console-log for the beta, and where a partial result belongs on screen is
    // a design question (openforge_catalog-ptt). The outcome is returned so a
    // caller can answer it without changing this.
    console.warn(
      `download: ${started.length} of ${urls.length} started; could not presign`,
      failed
    );
  }

  return { started, failed };
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

/** Where a blueprint's file is downloaded from. */
export function downloadUrl(blueprintId: string): string {
  return `/api/blueprints/${blueprintId}/download`;
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
    urls.push(downloadUrl(blueprint.id));
    processedBlueprints.add(blueprint.id);
  }

  // Add downloads for each selected part and its nested parts
  const processBlueprint = (bp: Blueprint) => {
    if (bp.file_name && !processedBlueprints.has(bp.id)) {
      urls.push(downloadUrl(bp.id));
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
