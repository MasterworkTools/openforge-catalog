'use client'

import React, { useState, useCallback, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { TagProvider, useTagContext } from '@/contexts/tag-context';
import type { TagNode } from '@/types';

interface AdminTagPickerProps {
  isOpen: boolean;
  onClose: () => void;
  onSelect: (tag: string[]) => void;
}

// Custom hook for debouncing
const useDebounce = <T,>(value: T, delay: number): T => {
  const [debouncedValue, setDebouncedValue] = useState<T>(value);
  useEffect(() => {
    const timer = setTimeout(() => setDebouncedValue(value), delay);
    return () => clearTimeout(timer);
  }, [value, delay]);
  return debouncedValue;
};

// Modified version of TagContainer that supports selection
const SelectableTagContainer = ({ onTagClick }: { onTagClick: (tag: string[]) => void }) => {
  const data = useTagContext((state) => state.data);
  const expandedNodes = useTagContext((state) => state.expandedNodes);
  const toggleNode = useTagContext((state) => state.toggleNode);
  const setSearchTerm = useTagContext((state) => state.setSearchTerm);
  const searchTerm = useTagContext((state) => state.searchTerm);
  const fetchTagDescriptions = useTagContext((state) => state.fetchTagDescriptions);
  const [searchInput, setSearchInput] = useState(searchTerm || "");
  const debouncedSearchInput = useDebounce(searchInput, 300);

  // Fetch tag descriptions on mount
  useEffect(() => {
    fetchTagDescriptions();
  }, [fetchTagDescriptions]);

  // Apply debounced search
  useEffect(() => {
    setSearchTerm(debouncedSearchInput.trim() || null);
  }, [debouncedSearchInput, setSearchTerm]);

  const handleSelectTag = useCallback((tagString: string) => {
    const tagArray = tagString.split('|');
    onTagClick(tagArray);
  }, [onTagClick]);

  const renderSelectableTags = (
    tagData: Record<string, TagNode>,
    level = 0
  ): React.ReactElement[] => {
    return Object.entries(tagData).map(([tag, value]) => {
      if (tag.startsWith('__') || tag === 'children') return null;

      const key = `${level}-${tag}`;
      const isExpanded = expandedNodes[key] || false;
      const hasChildren = value.children && Object.keys(value.children).length > 0;
      const fullTagName = value.__name as string;

      return (
        <div key={key} className="tagNode" style={{ marginLeft: level * 20 }}>
          <div style={{ display: 'flex', alignItems: 'center', whiteSpace: 'nowrap' }}>
            {hasChildren && (
              <span onClick={() => toggleNode(key)} className="expandButton">
                {isExpanded ? (
                  <svg width="14" height="14" viewBox="0 0 12 12" style={{ display: 'inline', verticalAlign: 'middle' }}>
                    <path d="M2 3L6 10L10 3Z" fill="currentColor"/>
                  </svg>
                ) : (
                  <svg width="14" height="14" viewBox="0 0 12 12" style={{ display: 'inline', verticalAlign: 'middle' }}>
                    <path d="M3 2L10 6L3 10Z" fill="currentColor"/>
                  </svg>
                )}
              </span>
            )}
            <span
              onClick={() => handleSelectTag(fullTagName)}
              style={{
                cursor: 'pointer',
                padding: '2px 6px',
                borderRadius: '3px',
                transition: 'background-color 0.2s'
              }}
              onMouseEnter={(e) => { e.currentTarget.style.backgroundColor = '#e0e0e0'; }}
              onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = 'transparent'; }}
            >
              {tag} {typeof value.__subTags === 'number' && value.__subTags > 0 && `(${value.__subTags})`}
            </span>
          </div>
          {isExpanded && hasChildren && value.children &&
            renderSelectableTags(value.children, level + 1)
          }
        </div>
      );
    }).filter(Boolean) as React.ReactElement[];
  };

  return (
    <div className="tag-container-wrapper">
      <div className="search-container" style={{ marginBottom: '1rem' }}>
        <input
          type="text"
          placeholder="Search tags..."
          value={searchInput}
          onChange={(e) => setSearchInput(e.target.value)}
          className="search-input"
          style={{ width: '100%' }}
        />
      </div>

      <div className="tag-tree-container">
        {renderSelectableTags(data, 0)}
      </div>
    </div>
  );
};

const AdminTagPicker = ({ isOpen, onClose, onSelect }: AdminTagPickerProps): React.ReactPortal | null => {
  if (!isOpen) return null;

  // Handler for tag selection
  const handleTagClick = (tag: string[]) => {
    onSelect(tag);
    onClose();
  };

  return createPortal(
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()} style={{ maxWidth: '600px', maxHeight: '80vh' }}>
        <div className="modal-header">
          <h3>Select Tag</h3>
          <button className="modal-close" onClick={onClose}>×</button>
        </div>

        <div className="modal-body" style={{ overflow: 'auto' }}>
          <TagProvider autoload={true} search_models={true} search_blueprints={true}>
            <SelectableTagContainer onTagClick={handleTagClick} />
          </TagProvider>
        </div>
      </div>
    </div>,
    document.body
  );
};

export default AdminTagPicker;
