'use client'

import React, { useState, useRef, useEffect } from 'react';
import { Blueprint, ConfigPart, ConfigTags } from '@/types';
import ConfigBox from './config-box';
import { useBlueprintContext } from '@/contexts/blueprint-context';

interface BlueprintConfigSectionProps {
  blueprint: Blueprint;
  nestedConfigs: Record<string, ConfigPart[]>;
  configValues?: { partName: string } | null;
}

const BlueprintConfigSection: React.FC<BlueprintConfigSectionProps> = ({
  blueprint,
  nestedConfigs,
  configValues
}) => {
  // Move hover state to top level
  const [hoveredKey, setHoveredKey] = useState<string | null>(null);
  const [tooltipDirection, setTooltipDirection] = useState<'up' | 'down'>('down');
  const hoverTimeout = useRef<NodeJS.Timeout | null>(null);
  const configSelections = useBlueprintContext((state) => state.configSelections);
  // Store refs for config boxes by key - using callback refs to avoid mutation during render
  const configBoxRefs = useRef<{ [key: string]: HTMLDivElement | null }>({});

  useEffect(() => {
    return () => {
      if (hoverTimeout.current) clearTimeout(hoverTimeout.current);
    };
  }, []);

  // Unified hover handler with direction logic
  const handleBoxHover = (isHovering: boolean, key: string) => {
    if (hoverTimeout.current) clearTimeout(hoverTimeout.current);
    if (isHovering) {
      // Clear any existing hover state immediately when starting to hover a new box
      setHoveredKey(null);
      hoverTimeout.current = setTimeout(() => {
        setHoveredKey(key);
        // Check direction
        const element = configBoxRefs.current[key];
        if (element) {
          const rect = element.getBoundingClientRect();
          const spaceBelow = window.innerHeight - rect.bottom;
          const tooltipHeight = 220; // estimate, or could measure
          if (spaceBelow < tooltipHeight && rect.top > tooltipHeight) {
            setTooltipDirection('up');
          } else {
            setTooltipDirection('down');
          }
        } else {
          setTooltipDirection('down');
        }
      }, 1000);
    } else {
      setHoveredKey(null);
    }
  };

  const renderTagRequirements = (tags: ConfigTags, part?: ConfigPart) => {
    const requirements = [];

    if (tags.require && tags.require.length > 0) {
      requirements.push(
        <div key="require" className="mt-2">
          <strong className="text-green-600">Required Tags:</strong>
          <ul className="list-disc pl-4">
            {tags.require.map((tag, index) => (
              <li key={index}>{tag.tag}</li>
            ))}
          </ul>
        </div>
      );
    }

    if (tags.accept && tags.accept.length > 0) {
      requirements.push(
        <div key="accept" className="mt-2">
          <strong className="text-blue-600">Accepted Tags:</strong>
          <ul className="list-disc pl-4">
            {tags.accept.map((tag, index) => (
              <li key={index}>{tag.tag}</li>
            ))}
          </ul>
        </div>
      );
    }

    if (tags.deny && tags.deny.length > 0) {
      requirements.push(
        <div key="deny" className="mt-2">
          <strong className="text-red-600">Denied Tags:</strong>
          <ul className="list-disc pl-4">
            {tags.deny.map((tag, index) => (
              <li key={index}>{tag.tag}</li>
            ))}
          </ul>
        </div>
      );
    }

    if (tags.constrain && tags.constrain.length > 0) {
      const tagConstraints = tags.constrain?.filter((c: { tag?: string; filter?: string }) => 'tag' in c) as { tag: string; siblings?: string[]; parent?: boolean }[];
      const filterConstraints = tags.constrain?.filter((c: { tag?: string; filter?: string }) => 'filter' in c) as { filter: string }[];

      if (tagConstraints.length > 0) {
        requirements.push(
          <div key="constrain" className="mt-2">
            <strong className="text-yellow-600">Constrained Tags (Inherited):</strong>
            <ul className="list-disc pl-4">
              {tagConstraints.map((constraint, index) => {
                const sourceInfo = [];
                if (constraint.parent !== false) {
                  sourceInfo.push('parent blueprint');
                }
                if (constraint.siblings !== undefined) {
                  if (constraint.siblings.length > 0) {
                    sourceInfo.push(`siblings: ${constraint.siblings.join(', ')}`);
                  } else {
                    sourceInfo.push('no siblings');
                  }
                } else {
                  sourceInfo.push('all siblings');
                }

                return (
                  <li key={index}>
                    <span className="font-medium">{constraint.tag}</span>
                    <span className="text-gray-600 text-xs ml-2">
                      (from {sourceInfo.join(', ')})
                    </span>
                  </li>
                );
              })}
            </ul>
            <div className="text-xs text-gray-500 mt-1">
              These tags are inherited from parent blueprint and/or sibling parts to ensure compatibility.
            </div>
          </div>
        );
      }

      if (filterConstraints.length > 0) {
        requirements.push(
          <div key="filter" className="mt-2">
            <strong className="text-purple-600">Constraint Filters:</strong>
            <ul className="list-disc pl-4">
              {filterConstraints.map((f, index) => (
                <li key={index}>
                  <span className="font-medium">{f.filter}</span>
                  <span className="text-gray-600 text-xs ml-2">
                    (excluded from inheritance)
                  </span>
                </li>
              ))}
            </ul>
            <div className="text-xs text-gray-500 mt-1">
              These tag prefixes are excluded from inherited constraints to prevent unwanted tag contamination.
            </div>
          </div>
        );
      }
    }

    if (part?.fulfills && part.fulfills.length > 0) {
      requirements.push(
        <div key="fulfills" className="mt-2">
          <strong className="text-emerald-600">Fulfills Requirements:</strong>
          <ul className="list-disc pl-4">
            {part.fulfills.map((fulfill, index) => (
              <li key={index}>
                <span className="font-medium">{fulfill.part}</span>
                <span className="text-gray-600 text-xs ml-2">
                  (satisfies this part requirement)
                </span>
              </li>
            ))}
          </ul>
          <div className="text-xs text-gray-500 mt-1">
            This part inherently includes functionality that would normally require separate parts.
          </div>
        </div>
      );
    }

    return requirements;
  };

  // Pass hoveredKey and handleBoxHover recursively
  const renderConfigBoxes = (parts: ConfigPart[], parentPath: string[] = [], parentFulfills: { part: string }[] = [], parentBlueprint?: Blueprint) => {
    return (
      <div className="relative">
        <div className="flex flex-wrap">
          {parts
            .filter(part => !parentFulfills.some(f => f.part === part.name))
            .map((part: ConfigPart) => {
              const partPath = [...parentPath, part.name];
              const key = partPath.join('|');
              return (
                <ConfigBox
                  key={key}
                  title={key}
                  value={part.tags}
                  optional={part.optional}
                  onHover={(isHovering) => handleBoxHover(isHovering, key)}
                  parentBlueprint={parentBlueprint}
                  peerParts={parts}
                  boxRef={(el: HTMLDivElement | null) => {
                    configBoxRefs.current[key] = el;
                  }}
                />
              );
            })}
        </div>
        {/* Only show tooltip for the globally hovered key */}
        {hoveredKey && parts.some(p => [...parentPath, p.name].join('|') === hoveredKey) && (
          <div
            className={`text-sm bg-white border rounded p-4 shadow-lg z-50 pointer-events-none max-w-md ${tooltipDirection === 'up' ? 'absolute bottom-full mb-2' : 'mt-2'}`}
            style={tooltipDirection === 'up' ? { left: 0 } : {}}
          >
            {(() => {
              const part = parts.find(p => {
                const partPath = [...parentPath, p.name];
                return partPath.join('|') === hoveredKey;
              });
              if (!part?.tags) return null;
              const tooltipContent = [];
              if (part.tags.constrain && part.tags.constrain.length > 0) {
                const hasParentInheritance = part.tags.constrain.some(c => 'tag' in c && c.parent !== false);
                const hasSiblingInheritance = part.tags.constrain.some(c => 'tag' in c);
                if (hasParentInheritance && parentBlueprint) {
                  tooltipContent.push(
                    <div key="parent-info" className="mb-2 p-2 bg-blue-50 rounded">
                      <strong className="text-blue-700 text-xs">Parent Blueprint Tags:</strong>
                      <div className="text-xs text-gray-600 mt-1">
                        {parentBlueprint.tags.slice(0, 5).join(', ')}
                        {parentBlueprint.tags.length > 5 && '...'}
                      </div>
                    </div>
                  );
                }
                if (hasSiblingInheritance && parts.length > 1) {
                  const siblingNames = parts
                    .filter(p => p.name !== part.name)
                    .map(p => p.name);
                  tooltipContent.push(
                    <div key="sibling-info" className="mb-2 p-2 bg-green-50 rounded">
                      <strong className="text-green-700 text-xs">Available Siblings:</strong>
                      <div className="text-xs text-gray-600 mt-1">
                        {siblingNames.join(', ')}
                      </div>
                    </div>
                  );
                }
              }
              tooltipContent.push(
                <div key="requirements">
                  {renderTagRequirements(part.tags, part)}
                </div>
              );
              return tooltipContent;
            })()}
          </div>
        )}
      </div>
    );
  };

  if (configValues) {
    return null;
  }

  return (
    <>
      {/* Main blueprint config parts */}
      {blueprint.blueprint_config?.parts && blueprint.blueprint_config.parts.length > 0 && (
        <div className="mt-4">
          <h3 className="text-xl font-semibold mb-2">Parts Needed to Build</h3>
          {renderConfigBoxes(
            blueprint.blueprint_config.parts,
            [],
            blueprint.blueprint_config.fulfills || [],
            blueprint
          )}
        </div>
      )}

      {/* Nested configs for selected parts */}
      {Object.entries(nestedConfigs).map(([partName, parts]) => {
        // Find fulfills for the part definition in the parent's config
        let fulfills: { part: string }[] = [];
        if (blueprint && blueprint.blueprint_config?.parts) {
          const parentPart = blueprint.blueprint_config.parts.find(p => p.name === partName);
          if (parentPart?.fulfills) {
            fulfills = parentPart.fulfills;
          }
        }
        // Filter parts to be shown
        const filteredParts = parts.filter(part => !fulfills.some(f => f.part === part.name));
        if (filteredParts.length === 0) return null;

        // Look up the selected blueprint for this partName
        const selectedParentBlueprint = configSelections[partName] || blueprint;

        return (
          <div key={partName} className="mt-4">
            <h3 className="text-xl font-semibold mb-2">Parts Needed for {partName}</h3>
            {renderConfigBoxes(filteredParts, [partName], fulfills, selectedParentBlueprint)}
          </div>
        );
      })}
    </>
  );
};

export default BlueprintConfigSection;
