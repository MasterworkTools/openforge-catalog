'use client'

import React from 'react';
import TagContainer from './tag-container';
import ResultsContainer from './results-container';
import BlueprintContainer from './blueprint-container';
import InstructionsPartSearch from './instructions-part-search';
import { BlueprintProvider } from '@/contexts/blueprint-context';
import { TagProvider } from '@/contexts/tag-context';
import { useBlueprintContext } from '@/contexts/blueprint-context';

const TabPartSearch: React.FC = () => {
  return (
    <TagProvider autoload={true} search_models={true} search_blueprints={false}>
      <BlueprintProvider autoload={true}>
        <div className='columnContainer'>
          <div className='tagContainerWrapper'>
            <TagContainer />
          </div>
          <div className='modelsContainerWrapper'>
            <ResultsContainer />
          </div>
          <div className='modelDetailsContainerWrapper'>
            <BlueprintSelector />
          </div>
        </div>
      </BlueprintProvider>
    </TagProvider>
  );
};

const BlueprintSelector: React.FC = () => {
  const blueprint = useBlueprintContext((state) => state.selectedBlueprint);
  return blueprint ? <BlueprintContainer /> : <InstructionsPartSearch />;
};

export default TabPartSearch;
