import { hostname, isDeepLink, productionHref } from '../environment-link';

const PRODUCTION = 'https://openforge.tools';

function at(pathname: string, search = '', hash = '') {
  return { pathname, search, hash };
}

describe('productionHref', () => {
  it('carries a blueprint deep link across', () => {
    expect(productionHref(PRODUCTION, at('/', '?blueprint_id=abc&md5=def'))).toBe(
      'https://openforge.tools/?blueprint_id=abc&md5=def',
    );
  });

  it('carries path, query and hash together', () => {
    expect(productionHref(PRODUCTION, at('/admin/', '?tab=blueprints', '#top'))).toBe(
      'https://openforge.tools/admin/?tab=blueprints#top',
    );
  });

  it('keeps an encoded URL in the query intact', () => {
    expect(productionHref(PRODUCTION, at('/', '?next=https%3A%2F%2Felsewhere.example'))).toBe(
      'https://openforge.tools/?next=https%3A%2F%2Felsewhere.example',
    );
  });

  it('falls back home for a protocol-relative path that would change origin', () => {
    expect(productionHref(PRODUCTION, at('//elsewhere.example/steal'))).toBe(PRODUCTION);
  });

  it('falls back home for a backslash-folded path', () => {
    expect(productionHref(PRODUCTION, at('///elsewhere.example'))).toBe(PRODUCTION);
  });

  it('falls back home when the configured production URL is not a URL', () => {
    expect(productionHref('not a url', at('/', '?blueprint_id=abc'))).toBe('not a url');
  });
});

describe('isDeepLink', () => {
  it.each([
    ['/', '', false],
    ['/', '?blueprint_id=abc', true],
    ['/admin/', '', true],
    ['//', '', false],
  ])('%s%s -> %s', (pathname, search, expected) => {
    expect(isDeepLink({ pathname, search })).toBe(expected);
  });
});

describe('hostname', () => {
  it('reduces a URL to its host', () => {
    expect(hostname('https://openforge.tools/somewhere')).toBe('openforge.tools');
  });

  it('returns the input when it is not a URL', () => {
    expect(hostname('openforge.tools')).toBe('openforge.tools');
  });
});
