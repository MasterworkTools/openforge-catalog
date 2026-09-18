'use client'

import React, { useState, useCallback, useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import { useTagContext } from '@/contexts/tag-context';
import type { TagNode } from '@/types';
import './tag-container.css';

const useDebounce = <T,>(value: T, delay: number): T => {
  const [debouncedValue, setDebouncedValue] = useState<T>(value);
  useEffect(() => {
    const timer = setTimeout(() => setDebouncedValue(value), delay);
    return () => clearTimeout(timer);
  }, [value, delay]);
  return debouncedValue;
};

const renderTags = (
  data: Record<string, TagNode>,
  level = 0,
  expandedNodes: Record<string, boolean>,
  toggleNode: (key: string) => void,
  handleAddTag: (tag: string) => void,
  handleAddDenyTag: (tag: string) => void,
  tagDescriptions: Record<string, string>,
  onTagHover: (tag: string | null, rect?: DOMRect) => void
) => {
  return Object.entries(data).map(([tag, value]) => {
    if (tag.startsWith('__') || tag === 'children') return null;

    const key = `${level}-${tag}`;
    const isExpanded = expandedNodes[key] || false;
    const hasChildren = value.children && Object.keys(value.children).length > 0;
    const description = tagDescriptions[value.__name as string];

    return (
      <div key={key} className="tagNode" style={{ marginLeft: level * 20 }}>
        <div style={{ display: 'flex', alignItems: 'center', whiteSpace: 'nowrap' }}>
          {hasChildren && (
            <span onClick={() => toggleNode(key)} className="expandButton">
              {hasChildren && (
                isExpanded ? (
                  <svg width="14" height="14" viewBox="0 0 12 12" style={{ display: 'inline', verticalAlign: 'middle' }} aria-label="collapse tag"><path d="M2 3L6 10L10 3Z" fill="currentColor"/></svg>
                ) : (
                  <svg width="14" height="14" viewBox="0 0 12 12" style={{ display: 'inline', verticalAlign: 'middle' }} aria-label="expand tag"><path d="M3 2L10 6L3 10Z" fill="currentColor"/></svg>
                )
              )}
            </span>
          )}
          <span
            className="group relative"
            onMouseEnter={e => {
              if (description) {
                const rect = (e.currentTarget as HTMLElement).getBoundingClientRect();
                onTagHover(value.__name as string, rect);
              }
            }}
            onMouseLeave={() => onTagHover(null)}
          >
            {tag} {typeof value.__subTags === 'number' && value.__subTags > 0 && `(${value.__subTags}) `}
            {value.__count && (
              <span className="tagButton">
                <button type="button" onClick={() => handleAddTag(value.__name as string)} className="font-bold cursor-pointer p-0 m-0 border-0 bg-transparent hover:bg-gray-200 rounded" aria-label={`Add tag ${value.__name}`}>+</button> <button type="button" onClick={() => handleAddDenyTag(value.__name as string)} className="font-bold text-red-600 cursor-pointer p-0 m-0 border-0 bg-transparent hover:bg-gray-200 rounded" aria-label={`Exclude tag ${value.__name}`}>-</button>
              </span>
            )}
            {description && (
              <span className="ml-1 text-gray-500 group-hover:text-gray-700">
                <svg className="w-4 h-4 inline" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-label="tag expanded">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              </span>
            )}
          </span>
        </div>
        {isExpanded && hasChildren && value.children && renderTags(value.children, level + 1, expandedNodes, toggleNode, handleAddTag, handleAddDenyTag, tagDescriptions, onTagHover)}
      </div>
    );
  });
};

const TagContainer = () => {
  const data = useTagContext((state) => state.data);
  const expandedNodes = useTagContext((state) => state.expandedNodes);
  const toggleNode = useTagContext((state) => state.toggleNode);
  const addTag = useTagContext((state) => state.addTag);
  const addDenyTag = useTagContext((state) => state.addDenyTag);
  const setSearchTerm = useTagContext((state) => state.setSearchTerm);
  const searchTerm = useTagContext((state) => state.searchTerm);
  const tagDescriptions = useTagContext((state) => state.tagDescriptions);
  const fetchTagDescriptions = useTagContext((state) => state.fetchTagDescriptions);
  const initialSetupComplete = useTagContext((state) => state.initialSetupComplete);
  const [searchInput, setSearchInput] = useState(searchTerm || "");
  const debouncedSearchInput = useDebounce(searchInput, 300);

  // Tooltip state
  const [hoveredTag, setHoveredTag] = useState<string | null>(null);
  const [tooltipRect, setTooltipRect] = useState<DOMRect | null>(null);
  const hoverTimeout = useRef<NodeJS.Timeout | null>(null);

  // Fetch tag descriptions on mount
  useEffect(() => {
    fetchTagDescriptions();
  }, [fetchTagDescriptions]);

  // Sync searchInput with searchTerm from store
  React.useEffect(() => {
    setSearchInput(searchTerm || "");
  }, [searchTerm]);

  // Apply debounced search (only after initial setup is complete)
  useEffect(() => {
    // Skip setting search term until initial URL parameter processing is complete
    if (initialSetupComplete) {
      setSearchTerm(debouncedSearchInput.trim() || null);
    }
  }, [debouncedSearchInput, setSearchTerm, initialSetupComplete]);

  // Cleanup hover timeout on unmount
  useEffect(() => {
    return () => {
      if (hoverTimeout.current) clearTimeout(hoverTimeout.current);
    };
  }, []);

  const handleAddTag = (tag: string) => {
    addTag(tag);
  };

  const handleAddDenyTag = (tag: string) => {
    addDenyTag(tag);
  };

  const handleSearchKeyDown = useCallback((e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      const term = searchInput.trim();
      setSearchTerm(term || null);
    }
  }, [searchInput, setSearchTerm]);

  const handleSearchChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    setSearchInput(e.target.value);
  }, []);

  // Tooltip handler with delay
  const handleTagHover = (tag: string | null, rect?: DOMRect) => {
    if (hoverTimeout.current) clearTimeout(hoverTimeout.current);
    if (tag && rect) {
      hoverTimeout.current = setTimeout(() => {
        setHoveredTag(tag);
        setTooltipRect(rect);
      }, 500);
    } else {
      setHoveredTag(null);
      setTooltipRect(null);
    }
  };

  return (
    <div className="tagContainer">
      <input
        type="text"
        value={searchInput}
        onChange={handleSearchChange}
        onKeyDown={handleSearchKeyDown}
        placeholder="Search blueprints..."
        style={{ backgroundColor: searchTerm ? '#f0f0f0' : 'white' }}
      />
      <div><strong>Browse Tags</strong></div>
      {/* False positive: renderTags is a pure function that doesn't use refs.
          The new experimental ESLint rule incorrectly flags recursive render functions
          as potential ref issues, but this is a standard React pattern for tree rendering. */}
      {/* eslint-disable-next-line react-hooks/refs */}
      <div>{renderTags(data, 0, expandedNodes, toggleNode, handleAddTag, handleAddDenyTag, tagDescriptions, handleTagHover)}</div>
      {hoveredTag && tooltipRect && tagDescriptions[hoveredTag] && createPortal(
        <div
          className="tooltip"
          style={{
            top: tooltipRect.top + tooltipRect.height + 4,
            left: Math.max(8, tooltipRect.left - 100)
          }}
        >
          {tagDescriptions[hoveredTag]}
        </div>,
        document.body
      )}
    </div>
  );
};

export default TagContainer;
