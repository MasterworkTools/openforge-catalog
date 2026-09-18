import { ConfigTags, Blueprint, ConfigPart } from '@/types';

export interface ProcessedTags {
  require: string[];
  deny: string[];
}

export interface SiblingSelection {
  partName: string;
  tags: string[];
}

/**
 * Filter out more specific tags from a set of tags.
 * A tag is considered more specific if it starts with another tag plus a pipe.
 * Exact matches for the constraint tag are always included.
 * @param tags - Set of tags to filter
 * @param constraintTag - The constraint tag that was used to collect these tags
 * @returns Set of most general tags plus exact matches
 */
function filterSpecificTags(tags: Set<string>, constraintTag: string): Set<string> {
  const result = new Set<string>();
  const tagsArray = Array.from(tags);

  // Always include exact matches for the constraint tag
  const exactMatches = tagsArray.filter(tag => tag === constraintTag);
  exactMatches.forEach(tag => result.add(tag));

  // For prefix matches (excluding exact matches), filter to most general
  const prefixMatches = tagsArray.filter(tag =>
    tag !== constraintTag && tag.startsWith(constraintTag + '|')
  );

  for (const tag of prefixMatches) {
    // Check if any other prefix match is a prefix of this tag
    let isMostGeneral = true;
    for (const otherTag of prefixMatches) {
      if (otherTag !== tag && tag.startsWith(otherTag + '|')) {
        isMostGeneral = false;
        break;
      }
    }
    if (isMostGeneral) {
      result.add(tag);
    }
  }

  return result;
}

/**
 * Process config values to extract require, deny, and constrain tags
 * @param configValues - The configuration tags to process
 * @param parentTags - Tags from the parent blueprint
 * @param siblingSelections - Array of sibling part selections with their tags
 * @returns Object containing require and deny tag arrays
 */
export function processConfigValues(
  configValues: ConfigTags | null,
  parentTags: string[] = [],
  siblingSelections: SiblingSelection[] = []
): ProcessedTags {
  const requireTags = new Set<string>();
  const denyTags = new Set<string>();

  if (!configValues) {
    return { require: [], deny: [] };
  }

  // Process require tags
  if (configValues.require) {
    configValues.require.forEach((data) => {
      if (data.tag) {
        requireTags.add(data.tag);
      }
    });
  }

  // Process deny tags
  if (configValues.deny) {
    configValues.deny.forEach((data) => {
      if (data.tag) {
        denyTags.add(data.tag);
      }
    });
  }

  // Process constrain tags
  if (configValues.constrain) {
    // Collect all filter values from constrain
    const filterTags = configValues.constrain
      .filter((c: { tag?: string; filter?: string }) => 'filter' in c)
      .map((c: { tag?: string; filter?: string }) => c.filter)
      .filter((filter): filter is string => filter !== undefined);

    // For each constraint tag type (e.g. 'texture', 'connection')
    configValues.constrain.forEach((data) => {
      if ('tag' in data && data.tag) {
        const constraintTag = data.tag;
        const siblings = data.siblings;
        const parent = data.parent !== false; // Default to true if not specified

        // Collect tags from allowed sources
        const allowedTags = new Set<string>();

        // Add parent tags if parent inheritance is enabled
        if (parent) {
          parentTags.forEach(tag => allowedTags.add(tag));
        }

        // Add sibling tags based on siblings configuration
        if (siblings === undefined) {
          // Default behavior: consider all siblings
          siblingSelections.forEach(sibling => {
            sibling.tags.forEach(tag => allowedTags.add(tag));
          });
        } else if (siblings.length > 0) {
          // Specific siblings only
          siblingSelections.forEach(sibling => {
            if (siblings.includes(sibling.partName)) {
              sibling.tags.forEach(tag => allowedTags.add(tag));
            }
          });
        }
        // If siblings is empty array, don't add any sibling tags

        // Filter tags that match the constraint type and don't match any filters
        const matchingTags = new Set<string>();
        const allowedTagsArray = Array.from(allowedTags);
        for (const tag of allowedTagsArray) {
          // Must match the constraint type
          if (!tag.startsWith(constraintTag)) {
            continue;
          }
          // Must not match any filters
          let shouldInclude = true;
          for (const filterTag of filterTags) {
            if (tag === filterTag || tag.startsWith(filterTag + '|') || filterTag.startsWith(tag + '|')) {
              shouldInclude = false;
              break;
            }
          }
          if (shouldInclude) {
            matchingTags.add(tag);
          }
        }

        // Add the most general version of each matching tag
        if (matchingTags.size > 0) {
          const generalTags = filterSpecificTags(matchingTags, constraintTag);
          generalTags.forEach(tag => requireTags.add(tag));
        }
      }
    });
  }

  return {
    require: Array.from(requireTags),
    deny: Array.from(denyTags)
  };
}

/**
 * Create a deep link URL with tags and optional search term
 * @param tags - Array of tags to include in the URL
 * @param searchTerm - Optional search term to include
 * @param denyTags - Array of deny tags to include in the URL
 * @returns URL query string
 */
export function createDeepLink(tags: string[], searchTerm?: string | null, denyTags?: string[]): string {
  const params = new URLSearchParams();
  tags.forEach(tag => params.append('tag', tag));
  denyTags?.forEach(tag => params.append('deny', tag));
  if (searchTerm) {
    params.set('search', searchTerm);
  }
  return params.toString();
}

/**
 * Build nested configs from configuration selections
 * @param configSelections - Current configuration selections
 * @returns Record of nested config parts by part name
 */
export function buildNestedConfigs(
  configSelections: Record<string, Blueprint>
): Record<string, ConfigPart[]> {
  const newNestedConfigs: Record<string, ConfigPart[]> = {};

  Object.entries(configSelections).forEach(([partName, bp]) => {
    if (bp.blueprint_config?.parts) {
      newNestedConfigs[partName] = bp.blueprint_config.parts;
    }
  });

  return newNestedConfigs;
}
