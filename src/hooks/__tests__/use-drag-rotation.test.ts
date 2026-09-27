import { act, renderHook } from '@testing-library/react';
import {
  stepView,
  useDragRotation,
  DRAG_THRESHOLD_PX,
  HORIZONTAL_VIEWS,
} from '../use-drag-rotation';

/**
 * Start a drag and move the pointer by `dx`, returning the step counts
 * the hook reported. The listeners live on the window, so the move is
 * dispatched there rather than on an element.
 */
function drag(dx: number, dy = 0): number[] {
  const steps: number[] = [];
  const { result } = renderHook(() =>
    useDragRotation({ onHorizontal: (n) => steps.push(n) })
  );
  act(() => {
    result.current.handleMouseDown({
      button: 0,
      clientX: 200,
      clientY: 200,
    } as React.MouseEvent);
  });
  act(() => {
    window.dispatchEvent(
      new MouseEvent('mousemove', { clientX: 200 + dx, clientY: 200 + dy })
    );
  });
  return steps;
}

describe('useDragRotation step counting', () => {
  it('truncates toward zero, so a leftward drag turns as far as a rightward one', () => {
    // One and a half thresholds is the smallest gesture where `floor`
    // and `trunc` disagree: `floor(-1.5)` is -2, one step further than
    // the same drag to the right would go.
    const far = Math.round(DRAG_THRESHOLD_PX * 1.5);
    expect(drag(far)).toEqual([1]);
    expect(drag(-far)).toEqual([-1]);
  });

  it('reports nothing below the threshold, in either direction', () => {
    expect(drag(DRAG_THRESHOLD_PX - 1)).toEqual([]);
    expect(drag(-(DRAG_THRESHOLD_PX - 1))).toEqual([]);
  });

  it('leaves a mostly-vertical drag to the vertical handler', () => {
    // The winning axis takes the whole gesture, so a sideways step is
    // not also reported on the way to a pole.
    expect(drag(DRAG_THRESHOLD_PX, DRAG_THRESHOLD_PX * 3)).toEqual([]);
  });
});

/**
 * The ring the parts list turns through. The gesture itself is
 * exercised through the page, where a drag has something to turn;
 * this is the arithmetic underneath it.
 */
describe('stepView', () => {
  it('steps forward and back round the ring', () => {
    expect(stepView('front', 1)).toBe('front-right');
    expect(stepView('front', -1)).toBe('front-left');
    expect(stepView('front', 2)).toBe('right');
  });

  it('wraps in both directions rather than stopping at the ends', () => {
    expect(stepView('front-left', 1)).toBe('front');
    expect(stepView('front', -1)).toBe('front-left');
    // A long drag is a lot of steps, not a clamp.
    expect(stepView('front', HORIZONTAL_VIEWS.length)).toBe('front');
    expect(stepView('front', -HORIZONTAL_VIEWS.length * 3 + 1)).toBe(
      'front-right'
    );
  });

  it('brings a pole back to the ring rather than doing nothing', () => {
    // Dragging sideways while looking at the top has to go somewhere;
    // the ring is measured from the front, so that is where it lands.
    expect(stepView('top', 0)).toBe('front');
    expect(stepView('bottom', 1)).toBe('front-right');
  });
});
