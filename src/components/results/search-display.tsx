import React from 'react';

interface SearchDisplayProps {
  searchTerm: string | null;
  onClearSearch: () => void;
}

export function SearchDisplay({ searchTerm, onClearSearch }: SearchDisplayProps) {
  if (!searchTerm) {
    return null;
  }

  return (
    <>
      <div className='selectedTagsContainer__header'>
        Search
      </div>
      <ul>
        <li>
          {searchTerm} <button className="tagButton" onClick={onClearSearch}>-</button>
        </li>
      </ul>
    </>
  );
}
