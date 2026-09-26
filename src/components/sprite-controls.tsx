'use client';

import React from 'react';

/**
 * The unwrapped cube: pick a side to look at.
 *
 * Shared by the blueprint sprite viewer and the guide's parts list.
 * Its second job is the more important one — dragging to spin is not
 * discoverable, and a widget that plainly offers "front, left, top"
 * says the picture turns without anyone having to write it down.
 *
 * Keyed by angle *name* rather than frame index, because the guide
 * turns several sheets at once and the name is the only thing they
 * have in common. The viewer maps its own indices to names.
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
  /**
   * Which sides exist. Everything in the layout, when not given —
   * every sheet in the catalog carries all ten, but a sheet that does
   * not should offer the sides it has rather than buttons that do
   * nothing.
   */
  available?: string[];
}

export function SpriteControls({ view, onView, available }: SpriteControlsProps) {
  const offered = Object.entries(LAYOUT).filter(
    ([name]) => !available || available.includes(name)
  );

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
