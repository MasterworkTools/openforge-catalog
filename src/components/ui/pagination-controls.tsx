import React from 'react';
import { Paging } from '@/types';

interface PaginationControlsProps {
  paging: Paging | null;
  startCount: number;
  endCount: number;
  totalCount: number;
  onPrevious: () => void;
  onNext: () => void;
}

export function PaginationControls({
  paging,
  startCount,
  endCount,
  totalCount,
  onPrevious,
  onNext
}: PaginationControlsProps) {
  return (
    <>
      <div className="totalCount">
        <strong>{startCount} - {endCount}</strong> of <strong>{totalCount}</strong> that match your tags
      </div>

      <div className="pagination flex justify-between mt-4">
        {paging?.previous_token && startCount > 1 && (
          <button
            onClick={onPrevious}
            className="px-4 py-2 text-sm bg-blue-500 text-white rounded hover:bg-blue-600"
          >
            Previous Page
          </button>
        )}
        <div className="flex-grow"></div>
        {paging?.next_token && endCount < totalCount && (
          <button
            onClick={onNext}
            className="px-4 py-2 text-sm bg-blue-500 text-white rounded hover:bg-blue-600"
          >
            Next Page
          </button>
        )}
      </div>
    </>
  );
}
