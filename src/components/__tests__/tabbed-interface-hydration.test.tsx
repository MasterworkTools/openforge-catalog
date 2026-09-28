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
 * Which tab opens is decided from the URL, and the *mechanism* is the
 * bug — not the outcome.
 *
 * The frontend is a static export: the HTML is prerendered at build
 * time with no `window`, so reading `location.search` in a `useState`
 * initialiser picks `partSearch` and bakes it into the markup. On the
 * real site `/?guide=wall` opened Part Search with no guide; in jsdom
 * the same code passed, because `render()` never does a server pass.
 *
 * So this renders to a string first — the markup the export ships — and
 * hydrates it against a URL, which is the only arrangement that can
 * tell an initialiser from an effect.
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

  it('opens the guides tab from a URL the prerender never saw', async () => {
    // The prerender has no URL at all, so its markup is Part Search.
    const markup = renderToString(<TabbedInterface />);
    expect(markup).toContain('part-search');

    // The browser then loads that markup at an address naming a guide.
    window.history.replaceState({}, '', '/?guide=wall');
    const host = document.createElement('div');
    host.innerHTML = markup;
    document.body.appendChild(host);

    await act(async () => {
      hydrateRoot(host, <TabbedInterface />);
    });

    const active = host.querySelector('button.tab.active');
    expect(active?.textContent).toBe('Guided Builds');

    host.remove();
  });
});
