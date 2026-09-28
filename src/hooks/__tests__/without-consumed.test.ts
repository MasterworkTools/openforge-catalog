import { CONSUMED, withoutConsumed } from '../use-url-parameters';

/**
 * Its own file, because `use-url-parameters.test.ts` replaces
 * `global.URLSearchParams` with a mock — a test written there would
 * prove things about the mock rather than about a URL.
 */
describe('withoutConsumed', () => {
  it('leaves parameters this hook does not own alone', () => {
    // The regression: it used to build the query from empty and re-add
    // only `blueprint_id`, eating everything else. Invisible while `/`
    // had nothing else in its query string, and then the Guided Builds
    // tab arrived — `/?guide=wall` was stripped to `/` on load, by a
    // hook inside the permanently-mounted Part Search tab, so a shared
    // guide link opened Part Search with no guide.
    const kept = new URLSearchParams(
      withoutConsumed('?guide=wall&method=s2w&texture=texture%7Ccave')
    );

    expect(kept.get('guide')).toBe('wall');
    expect(kept.get('method')).toBe('s2w');
    expect(kept.get('texture')).toBe('texture|cave');
  });

  it('removes every parameter it does consume', () => {
    // Asserted against `CONSUMED` rather than a hand-written list, so
    // adding a parameter to the hook without removing it here cannot
    // pass quietly.
    const search =
      '?' + CONSUMED.map((name) => `${name}=x`).join('&') + '&guide=wall';

    const kept = new URLSearchParams(withoutConsumed(search));

    for (const name of CONSUMED) {
      expect(kept.get(name)).toBeNull();
    }
    expect(kept.get('guide')).toBe('wall');
  });

  it('puts back the blueprint it is still using', () => {
    // The one it re-adds: the selection survives the cleanup that
    // strips its parameter, which is the hook's original purpose.
    const kept = new URLSearchParams(
      withoutConsumed('?blueprint_id=old&guide=wall', 'current')
    );

    expect(kept.get('blueprint_id')).toBe('current');
    expect(kept.get('guide')).toBe('wall');
  });

  it('is empty when there was nothing else', () => {
    expect(withoutConsumed('?tag=shape%7Cwall&deny=texture%7Ccave')).toBe('');
  });
});
