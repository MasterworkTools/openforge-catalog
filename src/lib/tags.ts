import type { Blueprint } from '@/types';

export function getOtherBlueprintTags(configSelections: Record<string, Blueprint>, title: string, blueprint: Blueprint): Set<string> {
  const otherBlueprintTags = new Set<string>();
  getParentBlueprintTags(configSelections, title, blueprint).forEach(tag => otherBlueprintTags.add(tag));
  getSelectionsWithSamePrefix(configSelections, title).forEach(([, bp]) => {
    if (bp.tags) {
      bp.tags.forEach((tag: string) => otherBlueprintTags.add(tag));
    }
  });
  return otherBlueprintTags;
}

export function getParentBlueprintTags(configSelections: Record<string, Blueprint>, title: string, blueprint: Blueprint): Set<string> {
  const tags = new Set<string>();
  if (title.includes('|')) {
    const parentKey = title.split('|').slice(0, -1).join('|');
    const parentBlueprint = configSelections[parentKey];
    if (parentBlueprint && parentBlueprint.tags) {
      parentBlueprint.tags.forEach((tag: string) => tags.add(tag));
    }
  } else {
    // No parentKey: use the top-level object (title itself)
    if (blueprint.tags) {
      blueprint.tags.forEach((tag: string) => tags.add(tag));
    }
  }
  return tags;
}

export function getSelectionsWithSamePrefix(configSelections: Record<string, Blueprint>, title: string): [string, Blueprint][] {
  if (title.includes('|')) {
    const currentPrefix = title.split('|')[0];
    return Object.entries(configSelections).filter(([key]) => key.split('|')[0] === currentPrefix);
  } else {
    // No prefix: only include entries without a prefix
    return Object.entries(configSelections).filter(([key]) => !key.includes('|'));
  }
}
