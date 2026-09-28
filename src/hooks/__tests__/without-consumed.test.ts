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
    // Named literally, not looped over `CONSUMED`. Building the input
    // *and* the expectation from the same constant is true whatever is
    // in it — dropping `search` from the list passed that version,
    // because the input stopped containing `search` too.
    //
    // These four are what `useUrlParameters` reads. If it learns a
    // fifth, this fails and should: leaving a consumed parameter on the
    // URL is the bug in the other direction.
    const kept = new URLSearchParams(
      withoutConsumed(
        '?tag=shape%7Cwall&deny=texture%7Ccave&search=wall' +
          '&blueprint_id=abc&md5=deadbeef&guide=wall'
      )
    );

    expect(kept.get('tag')).toBeNull();
    expect(kept.get('deny')).toBeNull();
    expect(kept.get('search')).toBeNull();
    expect(kept.get('blueprint_id')).toBeNull();
    // The other blueprint deep link, stripped for the same reason.
    expect(kept.get('md5')).toBeNull();
    expect(kept.get('guide')).toBe('wall');
    // And the list itself is those four, so the hook and this test
    // cannot drift apart silently.
    expect([...CONSUMED].sort()).toEqual([
      'blueprint_id',
      'deny',
      'md5',
      'search',
      'tag',
    ]);
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
