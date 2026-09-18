'use client'

import React, { useState, useEffect } from 'react';
import { Blueprint, CombinedBlueprintDocumentation } from '@/types';
import { DocumentationService } from '@/services/documentation-service';
import DocumentationTab from './blueprint/documentation-tab';
import ChangelogSection from './blueprint/changelog-section';

interface BlueprintDetailsTabsProps {
  children: React.ReactNode;
  blueprint: Blueprint;
}

const BlueprintDetailsTabs: React.FC<BlueprintDetailsTabsProps> = ({
  children,
  blueprint
}) => {
  const [activeTab, setActiveTab] = useState<'details' | 'documentation'>('details');
  const [documentation, setDocumentation] = useState<CombinedBlueprintDocumentation | null>(null);
  const [hasDocumentation, setHasDocumentation] = useState(false);

  // Reset to details tab whenever blueprint changes
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setActiveTab('details');
  }, [blueprint?.id]);

  useEffect(() => {
    const loadDocumentation = async () => {
      if (!blueprint?.id) {
        return;
      }

      try {
        const docs = await DocumentationService.getBlueprintAllDocumentation(blueprint.id);
        setDocumentation(docs);

        // Check if we have any documentation to show
        const hasBlueprintDocs = docs?.blueprint_documentation.some(doc => doc.document_type === 'instructions') || false;
        const hasTagDocs = Object.keys(docs?.tag_documentation || {}).length > 0;
        setHasDocumentation(hasBlueprintDocs || hasTagDocs);
      } catch (error) {
        console.error('Failed to load documentation:', error);
        setHasDocumentation(false);
      }
    };

    loadDocumentation();
  }, [blueprint?.id]);

  return (
    <div className="blueprintDetailsTabs">
      <div className="tabButtons">
        <button
          className={`tab ${activeTab === 'details' ? 'active' : ''}`}
          onClick={() => setActiveTab('details')}
        >
          Details
        </button>
        {hasDocumentation && (
          <button
            className={`tab ${activeTab === 'documentation' ? 'active' : ''}`}
            onClick={() => setActiveTab('documentation')}
          >
            Documentation
          </button>
        )}
      </div>
      <div className="tabContent">
        <div style={{ display: activeTab === 'details' ? 'block' : 'none' }}>
          {children}
          {documentation && <ChangelogSection changelogHistory={documentation.changelog_history} />}
        </div>
        {hasDocumentation && documentation && (
          <div style={{ display: activeTab === 'documentation' ? 'block' : 'none' }}>
            <DocumentationTab
              blueprintDocumentation={documentation.blueprint_documentation}
              tagDocumentation={documentation.tag_documentation}
            />
          </div>
        )}
      </div>
    </div>
  );
};

export default BlueprintDetailsTabs;
