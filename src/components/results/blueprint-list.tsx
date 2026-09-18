import React from 'react';
import { Blueprint } from '@/types';

interface BlueprintListProps {
  blueprints: Blueprint[];
  selectedBlueprint: Blueprint | null;
  onSelectBlueprint: (blueprint: Blueprint) => void;
}

export function BlueprintList({ blueprints, selectedBlueprint, onSelectBlueprint }: BlueprintListProps) {
  return (
    <ul>
      {blueprints.map((blueprint) => (
        <li
          key={blueprint.id}
          onClick={() => onSelectBlueprint(blueprint)}
          className={`blueprintListItem ${selectedBlueprint?.id === blueprint.id ? 'selected' : ''}`}
        >
          {blueprint.blueprint_name}
        </li>
      ))}
    </ul>
  );
}
