'use client'

import React, { useState, useRef, useEffect } from 'react';
import { useTagContext } from '@/contexts/tag-context';

interface TagRowProps {
  tags: string[];
  onTagClick: (tag: string) => void;
  tooltipAbove?: boolean;
}

const TagRow: React.FC<TagRowProps> = ({ tags, onTagClick, tooltipAbove = false }) => {
  const tagDescriptions = useTagContext((state) => state.tagDescriptions);
  const [hoveredTag, setHoveredTag] = useState<string | null>(null);
  const hoverTimeout = useRef<NodeJS.Timeout | null>(null);

  const handleMouseEnter = (tag: string) => {
    if (hoverTimeout.current) clearTimeout(hoverTimeout.current);
    hoverTimeout.current = setTimeout(() => setHoveredTag(tag), 500);
  };

  const handleMouseLeave = () => {
    if (hoverTimeout.current) clearTimeout(hoverTimeout.current);
    setHoveredTag(null);
  };

  useEffect(() => {
    return () => {
      if (hoverTimeout.current) clearTimeout(hoverTimeout.current);
    };
  }, []);

  return (
    <div className="flex flex-wrap gap-2 relative">
      {tags.map((tag) => {
        const description = tagDescriptions[tag];
        return (
          <div key={tag} className="group" onMouseEnter={() => handleMouseEnter(tag)} onMouseLeave={handleMouseLeave}>
            <button
              onClick={() => onTagClick(tag)}
              className="inline-block px-2 py-1 text-sm bg-blue-100 hover:bg-blue-200 rounded-md cursor-pointer"
            >
              {tag}
              {description && (
                <span className="ml-1 text-gray-500 group-hover:text-gray-700">
                  <svg className="w-4 h-4 inline" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-label="tag description">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                </span>
              )}
            </button>
            {description && hoveredTag === tag && (
              <div
                className={`absolute left-0 right-0 mx-auto ${tooltipAbove ? 'bottom-full mb-1' : 'top-full mt-1'} w-full max-w-full p-2 bg-gray-50 rounded-md shadow-lg text-sm text-gray-600 opacity-100 z-50 transition-opacity duration-150 pointer-events-none`}
              >
                {description}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
};

export default TagRow;
