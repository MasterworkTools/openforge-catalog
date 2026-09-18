'use client'

import React, { useState } from 'react';
import { Blueprint, ConfigTags, ConfigPart } from '@/types';
import { useBlueprintContext } from '@/contexts/blueprint-context';
import PartSelectionModal from '../part-selection-modal';
import { getOtherBlueprintTags } from '@/utils/tag-utils';

interface ConfigBoxProps {
  title: string;
  value: ConfigTags;
  optional?: boolean;
  onHover?: (isHovering: boolean) => void;
  parentBlueprint?: Blueprint;
  peerParts?: ConfigPart[];
  boxRef?: React.Ref<HTMLDivElement>;
}

const ConfigBox = ({ title, value, optional, onHover, parentBlueprint, boxRef }: ConfigBoxProps) => {
  const [isModalOpen, setIsModalOpen] = useState(false);
  const configSelections = useBlueprintContext((state) => state.configSelections);
  const setConfigSelection = useBlueprintContext((state) => state.setConfigSelection);
  const selectedBlueprint = configSelections[title];

  const handlePartSelected = (partName: string, blueprint: Blueprint) => {
    onHover?.(false);
    setConfigSelection(title, blueprint);
    setIsModalOpen(false);
  };

  const handleOpenModal = () => {
    onHover?.(false);
    setIsModalOpen(true);
  };

  const { parentTags, siblingSelections } = parentBlueprint ? getOtherBlueprintTags(configSelections, title, parentBlueprint) : { parentTags: [], siblingSelections: [] };

  return (
    <div
      className="border rounded p-4 mb-4 flex-1 min-w-[200px] mr-4 relative group"
      onMouseEnter={() => onHover?.(true)}
      onMouseLeave={() => onHover?.(false)}
      ref={boxRef}
    >
      <h3 className="text-lg font-semibold mb-2 cursor-help">
        {title}
        {optional && (
          <span className="ml-2 text-sm text-gray-500 bg-gray-100 px-2 py-1 rounded">
            Optional
          </span>
        )}
        <span className="ml-1 text-gray-500 group-hover:text-gray-700">
          <svg className="w-4 h-4 inline" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-label="tag description">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
        </span>
      </h3>
      {selectedBlueprint ? (
        <div className="mt-2">
          <div className="font-medium">{selectedBlueprint.blueprint_name}</div>
          {selectedBlueprint.images[0] && (
            <img
              src={selectedBlueprint.images[0].image_url}
              alt={selectedBlueprint.blueprint_name}
              className="mt-2 max-w-[200px] max-h-[200px] object-contain"
            />
          )}
          <button
            onClick={() => setConfigSelection(title, null)}
            className="mt-2 text-red-600 hover:text-red-800 text-sm font-medium"
          >
            Clear Selection
          </button>
        </div>
      ) : null}
      <button
        onClick={handleOpenModal}
        className="mt-2 text-blue-600 hover:text-blue-800 text-sm font-medium"
      >
        {selectedBlueprint ? 'Change Part' : 'Select Part'}
      </button>
      <PartSelectionModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        partName={title}
        configValues={value}
        onPartSelected={handlePartSelected}
        parentTags={parentTags}
        siblingSelections={siblingSelections}
      />
    </div>
  );
};

export default ConfigBox;
