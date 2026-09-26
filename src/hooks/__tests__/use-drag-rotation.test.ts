import { stepView, HORIZONTAL_VIEWS } from '../use-drag-rotation';

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
