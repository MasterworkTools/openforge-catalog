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
  return dragBoth(dx, dy).horizontal;
}

/**
 * The same gesture, reporting both axes — the winning axis takes the
 * whole drag, so which handler stayed silent is half the contract.
 */
function dragBoth(
  dx: number,
  dy = 0
): { horizontal: number[]; vertical: string[] } {
  const steps: number[] = [];
  const faces: string[] = [];
  const { result } = renderHook(() =>
    useDragRotation({
      onHorizontal: (n) => steps.push(n),
      onVertical: (f) => faces.push(f),
    })
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
  return { horizontal: steps, vertical: faces };
}

describe('useDragRotation step counting', () => {
  it('stops turning once the button comes up', () => {
    // The listeners are registered together and removed together, so
    // the gesture has to be shown live before it is shown dead: with
    // no mouseup listener the hook stays dragging and the pieces keep
    // spinning as the pointer crosses the page.
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
        new MouseEvent('mousemove', {
          clientX: 200 + DRAG_THRESHOLD_PX,
          clientY: 200,
        })
      );
    });
    expect(steps).toEqual([1]);
    act(() => {
      window.dispatchEvent(new MouseEvent('mouseup'));
    });
    expect(result.current.isDragging).toBe(false);
    act(() => {
      window.dispatchEvent(
        new MouseEvent('mousemove', {
          clientX: 200 + DRAG_THRESHOLD_PX * 3,
          clientY: 200,
        })
      );
    });
    expect(steps).toEqual([1]);
  });

  it('truncates toward zero, so a leftward drag turns as far as a rightward one', () => {
    // Any drag between one threshold and two shows it, since below one
    // nothing is reported at all: `floor(-1.5)` is -2, one step further
    // than the same drag to the right would go. 1.5 is the middle of
    // that range rather than a uniquely minimal case.
    const far = Math.round(DRAG_THRESHOLD_PX * 1.5);
    expect(drag(far)).toEqual([1]);
    expect(drag(-far)).toEqual([-1]);
  });

  it('reports nothing below the threshold, and one step exactly on it', () => {
    expect(drag(DRAG_THRESHOLD_PX - 1)).toEqual([]);
    expect(drag(-(DRAG_THRESHOLD_PX - 1))).toEqual([]);
    // Exactly on the threshold counts, so `>=` is not `>`. Every other
    // distance here is 29, 45, 60 or 90, which cannot tell them apart.
    expect(drag(DRAG_THRESHOLD_PX)).toEqual([1]);
    expect(drag(-DRAG_THRESHOLD_PX)).toEqual([-1]);
    expect(dragBoth(0, DRAG_THRESHOLD_PX).vertical).toEqual(['bottom']);
  });

  it('gives a mostly-vertical drag to the vertical handler, and only it', () => {
    // The winning axis takes the whole gesture, so a sideways step is
    // not also reported on the way to a pole — and the pole it reports
    // has to be the right one, since the polarity is now shared by two
    // components rather than owned by one.
    const down = dragBoth(DRAG_THRESHOLD_PX, DRAG_THRESHOLD_PX * 3);
    expect(down.horizontal).toEqual([]);
    expect(down.vertical).toEqual(['bottom']);

    const up = dragBoth(DRAG_THRESHOLD_PX, -DRAG_THRESHOLD_PX * 3);
    expect(up.horizontal).toEqual([]);
    expect(up.vertical).toEqual(['top']);
  });

  it('does nothing at all for an exact diagonal, which has no winner', () => {
    // "Whichever axis is winning takes the gesture" means a tie has no
    // winner. This is the only case the `absX > absY` term decides —
    // the vertical branch already claims everything mostly-vertical —
    // so without it every exact diagonal would resolve to a sideways
    // turn, which is one reading of an ambiguous gesture asserted as
    // if it were the only one.
    const even = dragBoth(DRAG_THRESHOLD_PX * 2, DRAG_THRESHOLD_PX * 2);
    expect(even.horizontal).toEqual([]);
    expect(even.vertical).toEqual([]);
  });

  it('gives a mostly-sideways drag to the horizontal handler, and only it', () => {
    // The other side of the same rule, which was unheld: without it
    // the axis test could be dropped and every sideways drag would
    // also jump to a pole.
    const across = dragBoth(DRAG_THRESHOLD_PX * 3, DRAG_THRESHOLD_PX);
    expect(across.horizontal).toEqual([3]);
    expect(across.vertical).toEqual([]);
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
