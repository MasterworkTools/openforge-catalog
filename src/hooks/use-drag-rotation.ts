'use client';

import { useCallback, useEffect, useRef, useState } from 'react';

/**
 * Drag-to-spin, shared by the blueprint sprite viewer and the guide's
 * parts list.
 *
 * The two want the same gesture and disagree about what it turns. The
 * viewer spins one sheet and thinks in that sheet's frame indices; the
 * parts list spins four pieces at once and thinks in angle *names*,
 * because the pieces are different sheets and only the name is common
 * to all of them. So this hook owns the gesture — where the drag
 * started, which axis won, how far counts as a step — and hands out
 * the step count, leaving what a step means to the caller.
 *
 * Every sheet in the catalog carries the same ten angles in the same
 * order, so the ring below is the whole vocabulary rather than a
 * guess: the eight around the equator, then top and bottom.
 */

export const HORIZONTAL_VIEWS = [
  'front',
  'front-right',
  'right',
  'back-right',
  'back',
  'back-left',
  'left',
  'front-left',
] as const;

export type HorizontalView = (typeof HORIZONTAL_VIEWS)[number];
export type VerticalView = 'top' | 'bottom';

/** How far the pointer travels before it counts as one step round. */
export const DRAG_THRESHOLD_PX = 30;

interface DragRotationHandlers {
  /** Called on mouse down, for the caller to snapshot where it was. */
  onStart?: () => void;
  /** Steps since the drag began — signed, and relative, not absolute. */
  onHorizontal: (steps: number) => void;
  /** A decisive up or down drag, which goes straight to a pole. */
  onVertical?: (face: VerticalView) => void;
}

export function useDragRotation({
  onStart,
  onHorizontal,
  onVertical,
}: DragRotationHandlers) {
  const [isDragging, setIsDragging] = useState(false);
  const startX = useRef(0);
  const startY = useRef(0);

  const handleMouseDown = useCallback(
    (e: React.MouseEvent) => {
      // Left button only: the others belong to the context menu, and
      // capturing them makes a right-click feel broken.
      if (e.button !== 0) return;
      setIsDragging(true);
      startX.current = e.clientX;
      startY.current = e.clientY;
      onStart?.();
    },
    [onStart]
  );

  const handleMouseMove = useCallback(
    (e: MouseEvent) => {
      if (!isDragging) return;
      const deltaX = e.clientX - startX.current;
      const deltaY = e.clientY - startY.current;
      const absX = Math.abs(deltaX);
      const absY = Math.abs(deltaY);

      // Whichever axis is winning takes the gesture, so a drag that is
      // mostly sideways never jumps to a pole on the way.
      if (absY > absX && absY >= DRAG_THRESHOLD_PX) {
        onVertical?.(deltaY < 0 ? 'top' : 'bottom');
      } else if (absX > absY && absX >= DRAG_THRESHOLD_PX) {
        onHorizontal(Math.floor(deltaX / DRAG_THRESHOLD_PX));
      }
    },
    [isDragging, onHorizontal, onVertical]
  );

  const handleMouseUp = useCallback(() => setIsDragging(false), []);

  // On the window rather than the element: a drag that leaves the
  // picture should keep turning it, and should end when the button
  // comes up wherever that happens.
  useEffect(() => {
    if (!isDragging) return;
    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('mouseup', handleMouseUp);
    return () => {
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isDragging, handleMouseMove, handleMouseUp]);

  return { handleMouseDown, isDragging };
}

/**
 * Step round the ring, wrapping in both directions.
 *
 * Takes any angle name, not just a ring member: dragging sideways
 * while looking at the top or the bottom should come back to the ring
 * rather than do nothing, and it lands at the front, which is where
 * the ring is measured from.
 */
export function stepView(from: string, steps: number): HorizontalView {
  const at = (HORIZONTAL_VIEWS as readonly string[]).indexOf(from);
  const start = at === -1 ? 0 : at;
  const n = HORIZONTAL_VIEWS.length;
  return HORIZONTAL_VIEWS[(((start + steps) % n) + n) % n];
}
