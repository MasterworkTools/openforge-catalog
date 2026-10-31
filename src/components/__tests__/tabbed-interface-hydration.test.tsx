import React from 'react';
import { renderToString } from 'react-dom/server';
import { hydrateRoot } from 'react-dom/client';
import { act } from '@testing-library/react';
import TabbedInterface from '../tabbed-interface';

jest.mock('../tab-part-search', () => ({
  __esModule: true,
  default: () => <div data-testid="part-search" />,
}));
jest.mock('../tab-admin', () => ({
  __esModule: true,
  default: () => <div data-testid="admin" />,
}));
jest.mock('../part-selection-modal', () => ({
  __esModule: true,
  default: () => null,
}));
jest.mock('@/contexts/admin-context', () => ({
  useAdminContext: () => ({ state: { isAuthenticated: false } }),
}));
jest.mock('@/utils/app-config', () => ({
  loadAppConfig: () => Promise.resolve({}),
}));

/**
 * The frontend is a static export, so the markup is prerendered with
 * no `window` and the browser hydrates it at a real address. The tab
 * the strip shows has to be the same in both, or React discards the
 * server markup and the first paint flickers.
 *
 * Guided Builds is the tab the site opens on, which is why this no
 * longer tests a flip: it tests that nothing flips. `render()` never
 * does a server pass, so a string render followed by `hydrateRoot` is
 * the only arrangement that can tell the two apart.
 */
describe('TabbedInterface, hydrated', () => {
  const realFetch = global.fetch;

  beforeEach(() => {
    global.fetch = jest.fn((): Promise<unknown> =>
      Promise.resolve({
        ok: false,
        status: 404,
        json: () => Promise.resolve({ guides: [] }),
      })
    ) as unknown as typeof global.fetch;
  });

  afterEach(() => {
    global.fetch = realFetch;
    window.history.replaceState({}, '', '/');
  });

  it.each([
    ['an address naming a guide', '/?guide=wall'],
    ['a bare address', '/'],
  ])('stays on Guided Builds when hydrated at %s', async (_what, url) => {
    // The prerender has no URL at all, and its markup already shows
    // the landing tab active.
    const markup = renderToString(<TabbedInterface />);
    expect(markup).toContain('tab active');

    window.history.replaceState({}, '', url);
    const host = document.createElement('div');
    host.innerHTML = markup;
    document.body.appendChild(host);

    const warn = jest.spyOn(console, 'error').mockImplementation(() => {});
    await act(async () => {
      hydrateRoot(host, <TabbedInterface />);
    });

    const active = host.querySelector('button.tab.active');
    expect(active?.textContent).toBe('Guided Builds');
    // A tab mismatch between the two passes is what this exists to
    // catch, and React reports it through console.error.
    expect(
      warn.mock.calls.filter((c) => /hydrat/i.test(String(c[0])))
    ).toHaveLength(0);
    warn.mockRestore();

    host.remove();
  });
});
