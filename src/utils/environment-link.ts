/**
 * Where the environment banner points, and how it describes itself.
 *
 * Pure functions over a location rather than reads of `window`, so the
 * origin-escape cases below can be tested without a browser.
 */

export type PageLocation = Pick<Location, 'pathname' | 'search' | 'hash'>;

/**
 * The same page on production, so a deep link someone followed into staging keeps
 * working: blueprint links carry their identifier in the query string, so the query
 * has to travel with the path.
 *
 * A protocol-relative path ("//elsewhere") resolves against the scheme rather than
 * the base, so anything that lands off the production origin falls back to its home page.
 */
export function productionHref(productionUrl: string, location: PageLocation): string {
  try {
    const target = new URL(`${location.pathname}${location.search}${location.hash}`, productionUrl);
    return target.origin === new URL(productionUrl).origin ? target.toString() : productionUrl;
  } catch {
    return productionUrl;
  }
}

/** A bare home page needs no "this page" phrasing. */
export function isDeepLink(location: Pick<PageLocation, 'pathname' | 'search'>): boolean {
  return location.search.length > 0 || location.pathname.replace(/\/+$/, '') !== '';
}

/** Hostname alone reads better in a sentence than the full URL. */
export function hostname(url: string): string {
  try {
    return new URL(url).hostname;
  } catch {
    return url;
  }
}
