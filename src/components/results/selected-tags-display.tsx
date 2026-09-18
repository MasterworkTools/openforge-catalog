import React from 'react';
import { ConfigTags } from '@/types';
import { SearchDisplay } from './search-display';

interface SelectedTagsDisplayProps {
  selectedTags: string[];
  denyTags: string[];
  searchTerm: string | null;
  configValues?: ConfigTags | null;
  isTagRemovable: (tag: string) => boolean;
  onRemoveTag: (tag: string) => void;
  onClearSearch: () => void;
  onCreateDeepLink: () => string;
  onCopyToClipboard: (text: string) => void;
  copied: boolean;
}

export function SelectedTagsDisplay({
  selectedTags,
  denyTags,
  searchTerm,
  configValues,
  isTagRemovable,
  onRemoveTag,
  onClearSearch,
  onCreateDeepLink,
  onCopyToClipboard,
  copied
}: SelectedTagsDisplayProps) {
  if (selectedTags.length === 0 && denyTags.length === 0 && !searchTerm) {
    return null;
  }

  return (
    <div className='selectedTagsContainer'>
      {!configValues && (selectedTags.length > 0 || denyTags.length > 0 || searchTerm) && (
        <div className='selectedTagsContainer__header'>
          <a className='visibleLink' href={"/?" + onCreateDeepLink()}>deeplink</a>&nbsp;
          <button title={copied ? "url copied" : "Copy url to clipboard"} onClick={() => onCopyToClipboard(onCreateDeepLink())}>
            <svg aria-hidden="true" focusable="false" className="octicon octicon-copy" viewBox="0 0 16 16" width="16" height="16" fill="currentColor" display="inline-block" overflow="visible">
              <path d="M0 6.75C0 5.784.784 5 1.75 5h1.5a.75.75 0 0 1 0 1.5h-1.5a.25.25 0 0 0-.25.25v7.5c0 .138.112.25.25.25h7.5a.25.25 0 0 0 .25-.25v-1.5a.75.75 0 0 1 1.5 0v1.5A1.75 1.75 0 0 1 9.25 16h-7.5A1.75 1.75 0 0 1 0 14.25Z"></path>
              <path d="M5 1.75C5 .784 5.784 0 6.75 0h7.5C15.216 0 16 .784 16 1.75v7.5A1.75 1.75 0 0 1 14.25 11h-7.5A1.75 1.75 0 0 1 5 9.25Zm1.75-.25a.25.25 0 0 0-.25.25v7.5c0 .138.112.25.25.25h7.5a.25.25 0 0 0 .25-.25v-7.5a.25.25 0 0 0-.25-.25Z"></path>
            </svg>
          </button>
        </div>
      )}
      <div className='flex justify-between'>
        {(selectedTags.length > 0 || searchTerm) && (
          <div className='flex-1'>
            <SearchDisplay
              searchTerm={searchTerm}
              onClearSearch={onClearSearch}
            />
            {selectedTags.length > 0 && (
              <>
                <div className='selectedTagsContainer__header'>
                  Selected Tags
                </div>
                <ul>
                  {Array.from(new Set(selectedTags)).map((tag) => (
                    <li key={tag}>
                      {tag} {isTagRemovable(tag) && <button className="tagButton" onClick={() => onRemoveTag(tag)}>-</button>}
                    </li>
                  ))}
                </ul>
              </>
            )}
          </div>
        )}
        {denyTags.length > 0 && (
          <div className={selectedTags.length > 0 || searchTerm ? 'flex-1 ml-4' : 'flex-1'}>
            <div className='selectedTagsContainer__header'>
              Denied Tags
            </div>
            <ul>
              {denyTags.map((tag) => (
                <li key={tag} className="text-red-600">
                  {tag} {isTagRemovable(tag) && <button className="tagButton" onClick={() => onRemoveTag(tag)}>-</button>}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}
