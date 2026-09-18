'use client'

import React from 'react';
import ReactMarkdown from 'react-markdown';
import { ChangelogHistory } from '@/types';

interface ChangelogSectionProps {
  changelogHistory: ChangelogHistory;
}

const ChangelogSection: React.FC<ChangelogSectionProps> = ({ changelogHistory }) => {
  if (!changelogHistory.changelogs.length) {
    return null;
  }

  const formatDate = (dateString: string | null): string => {
    if (!dateString) return 'Unknown date';
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric'
    });
  };

  const getVersionLabel = (versionNumber: number, deprecated: boolean, isLatest: boolean): string => {
    if (isLatest && !deprecated) return `Version ${versionNumber} (Current Version)`;
    if (deprecated) return `Version ${versionNumber} (Deprecated)`;
    return `Version ${versionNumber}`;
  };

  return (
    <div className="changelog-section mt-8 pt-6 border-t border-gray-200">
      <h3 className="text-lg font-semibold mb-4 text-gray-800">Version History</h3>

      <div className="space-y-4">
        {changelogHistory.changelogs.slice().reverse().map((entry, index) => {
          // Calculate version number: depth 0 is version 1, depth 1 is version 2, etc.
          const versionNumber = entry.depth + 1;
          const isInitialVersion = entry.depth === 0; // Depth 0 is always the initial version

          return (
          <div key={`${entry.blueprint_id}-${entry.depth}`} className="changelog-entry">
              <div className="flex items-start gap-3">
                <div className="flex-shrink-0">
                  <div className="w-2 h-2 bg-gray-400 rounded-full mt-2"></div>
                </div>
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-2">
                    <h4 className="font-medium text-gray-700">
                      {getVersionLabel(versionNumber, entry.deprecated, index === 0)}
                    </h4>
                    <span className="text-sm text-gray-500">
                      {formatDate(entry.created_at)}
                    </span>
                    {entry.deprecated && (
                      <span className="text-xs bg-red-100 text-red-800 px-2 py-1 rounded">
                        {entry.successor_id ? 'Deprecated' : 'End of Life'}
                      </span>
                    )}
                  </div>

                  {entry.changelog ? (
                    <div className="prose prose-sm max-w-none text-gray-600">
                      <ReactMarkdown>{entry.changelog}</ReactMarkdown>
                    </div>
                  ) : (
                    <p className="text-sm text-gray-500 italic">
                      {/* Check if this is the first version (depth 0) */}
                      {isInitialVersion
                        ? 'Initial version'
                        : 'No changelog available for this version.'}
                    </p>
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {changelogHistory.has_more && (
        <div className="mt-4 text-center">
          <p className="text-sm text-gray-500">
            Showing {changelogHistory.changelogs.length} of {changelogHistory.total_count} versions
          </p>
        </div>
      )}
    </div>
  );
};

export default ChangelogSection;
