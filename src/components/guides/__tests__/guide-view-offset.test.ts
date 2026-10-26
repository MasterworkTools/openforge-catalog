import { viewFor } from '@/hooks/use-drag-rotation';

/**
 * A corner's pieces face outward in different directions, so a role can
 * name the angle it reads best from. The point of these is that it is
 * an OFFSET: turn the list and every piece turns with it, each holding
 * its own quarter, rather than one piece pinned while the rest move.
 */
describe('viewFor', () => {
  it('leaves a part with no angle of its own where the list is', () => {
    expect(viewFor({}, 'front-left')).toBe('front-left');
    expect(viewFor({ view: null }, 'back')).toBe('back');
  });

  it('holds a named part at its offset from where the list starts', () => {
    // front-left is the list's start, so front-right is two steps round
    expect(viewFor({ view: 'front-right' }, 'front-left')).toBe('front-right');
    expect(viewFor({ view: 'back-right' }, 'front-left')).toBe('back-right');
  });

  it('keeps that offset as the list turns', () => {
    // the whole list one step round: every piece follows, gap intact
    expect(viewFor({ view: 'front-right' }, 'front')).toBe('right');
    expect(viewFor({ view: 'back-right' }, 'front')).toBe('back');
    // and all the way round, where it wraps
    expect(viewFor({ view: 'front-right' }, 'left')).toBe('front');
  });

  it('turns with the list when the angle is off the ring', () => {
    // top and bottom are not on the ring, so an offset into it means
    // nothing and the piece simply shows what the list shows
    expect(viewFor({ view: 'front-right' }, 'top')).toBe('top');
    expect(viewFor({ view: 'nonsense' }, 'front')).toBe('front');
  });
});
