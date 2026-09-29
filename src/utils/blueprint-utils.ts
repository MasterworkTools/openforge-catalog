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
 * the transfer. Measured on production, that redirect takes ~4.7 s on a cold
 * Lambda and ~0.3 s warm, so a cold start missed the old budget outright and a
 * warm one missed it for anyone far from us-east or on cellular
 * (openforge_catalog-m8i, reported from New Zealand).
 *
 * A minute is not a considered number; it is "longer than any download takes to
 * *start*". Starting is the only thing it has to outlast: once a response has
 * become a download the browser owns it, not the iframe, so a transfer still in
 * flight at 60 s is not affected — only a request that has not yet become a
 * download can be aborted. Removing the iframe is therefore tidiness rather
 * than correctness, and if that ever looks doubtful the timer can simply go.
 */
const DOWNLOAD_IFRAME_LIFETIME_MS = 60_000;

/**
 * Download one or many files.
 *
 * One file is a plain navigation: the response is an attachment, so the browser
 * downloads it and stays put, and there is nothing to race.
 *
 * Many files cannot each be a navigation, so each gets a hidden iframe that
 * lives long enough for the request to start. Nothing paces them: measured on
 * production in Chromium and Firefox, six files at zero spacing delivered 6/6
 * in every trial, including a run whose last three requests landed on cold
 * execution environments 3.7–5.1 s in. The lifetime absorbs that, which is why
 * no stagger and no pre-flight are needed.
 *
 * ponytail: N files means N simultaneous requests, so up to N cold starts, and
 * up to N*4 Aurora sessions rather than N — openforge/db/__init__.py opens a
 * 4-connection pool per container and Lambda only ever uses one of them
 * (openforge_catalog-505). Measured clean at 12 and 25 concurrent against
 * production, and N is a guide's roles or a blueprint's config selections, never
 * the catalog. The bound that bites first is not N but 50/N *overlapping*
 * Download-alls, since reserved_concurrent_executions = 50 is shared with all
 * other API traffic. So if N grows, or this button becomes common enough to
 * overlap, the first lever is that pool (min_size=1, max_size=2), not spacing
 * these out.
 */
export const downloadFiles = (urls: string[], nav: (url: string) => void = navigate): void => {
  if (urls.length === 1) {
    nav(urls[0]);
    return;
  }

  for (const url of urls) {
    const iframe = document.createElement('iframe');
    iframe.style.display = 'none';

    // A file that downloads never commits a document, so the frame stays on the
    // readable, empty about:blank it inherited. Anything with *content* here is
    // therefore a failure, and there are two kinds: R2 refusing the object
    // (cross-origin, so unreadable — `contentDocument` is null) and our own API
    // 404ing (same-origin, so its error body can be printed). Measured in both
    // engines, including against deliberately stalled responses: exactly one
    // `load` per URL, and on success Firefox reports a readable empty document
    // while Chromium fires nothing. So emptiness is the success signal — `load`
    // alone would be a false positive on every Firefox download.
    //
    // Worth these lines because it is the only report of a download that failed
    // *past* the redirect, and because Chromium logs R2's 403 itself while
    // Firefox logs nothing at all — which is the browser this was reported from.
    // Passive: it watches the real download, adds no request and gates nothing,
    // so unlike a pre-flight check it cannot fail closed. Putting it on screen is
    // openforge_catalog-ptt.
    //
    // If a future CSP pass ever adds `iframe.sandbox`, an opaque origin reads
    // null unconditionally and this inverts into a warning on every success.
    iframe.addEventListener('load', () => {
      let body: string;
      try {
        // A null document is the opaque cross-origin case. A document that is
        // merely bodyless is not a failure, so it must not read as one.
        const doc = iframe.contentDocument;
        body = doc === null ? '(cross-origin)' : (doc.body?.textContent ?? '');
      } catch {
        body = '(cross-origin)';
      }
      if (body.trim()) console.warn('download did not start:', url, body.slice(0, 200));
    });

    iframe.src = url;
    document.body.appendChild(iframe);

    setTimeout(() => iframe.remove(), DOWNLOAD_IFRAME_LIFETIME_MS);
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
