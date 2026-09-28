'use client';

import React from 'react';

/**
 * The unwrapped cube: pick a side to look at.
 *
 * The guide's parts list uses this one. `sprite-viewer.tsx` keeps its
 * own and the two were not unified — but not for the reason first
 * written here: the viewer also works from angle names and maps them
 * to indices itself. The real difference is that it omits a button
 * for a side its sheet does not carry, which one widget turning
 * several sheets at once cannot do, because the sides they are
 * missing differ. `useDragRotation` is the part that is genuinely
 * shared.
 *
 * Its second job is the more important one — dragging to spin is not
 * discoverable, and a widget that plainly offers "front, left, top"
 * says the picture turns without anyone having to write it down.
 */

/** Where each side sits in the flattened cube, and its short label. */
const LAYOUT: Record<string, { label: string; row: number; col: number }> = {
  top: { label: 'TOP', row: 0, col: 1 },
  'front-left': { label: 'FL', row: 1, col: 0 },
  front: { label: 'F', row: 1, col: 1 },
  'front-right': { label: 'FR', row: 1, col: 2 },
  left: { label: 'L', row: 2, col: 0 },
  right: { label: 'R', row: 2, col: 2 },
  'back-left': { label: 'BL', row: 3, col: 0 },
  back: { label: 'B', row: 3, col: 1 },
  'back-right': { label: 'BR', row: 3, col: 2 },
  bottom: { label: 'BOT', row: 4, col: 1 },
};

interface SpriteControlsProps {
  /** The side currently shown, by name. */
  view: string;
  onView: (name: string) => void;
}

export function SpriteControls({ view, onView }: SpriteControlsProps) {
  // Every sheet in the catalog carries all ten sides, so the layout
  // is the offer. A per-sheet subset was written for and never used;
  // add it back the day a sheet ships with fewer.
  const offered = Object.entries(LAYOUT);

  return (
    <div
      role="group"
      aria-label="Which side to look at"
      className="grid grid-cols-3 gap-1"
      style={{ width: '120px' }}
    >
      {[0, 1, 2, 3, 4].map((row) =>
        [0, 1, 2].map((col) => {
          const found = offered.find(
            ([, pos]) => pos.row === row && pos.col === col
          );
          if (!found) return <div key={`${row}-${col}`} className="w-9 h-8" />;

          const [name, pos] = found;
          const active = view === name;
          return (
            <button
              key={`${row}-${col}`}
              type="button"
              onClick={() => onView(name)}
              aria-pressed={active}
              aria-label={name}
              title={name}
              className={`w-9 h-8 text-xs font-medium rounded transition-colors ${
                active
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-200 hover:bg-gray-300 text-gray-700'
              }`}
            >
              {pos.label}
            </button>
          );
        })
      )}
    </div>
  );
}
