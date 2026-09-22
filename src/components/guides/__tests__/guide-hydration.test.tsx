import React from 'react';
import { renderToString } from 'react-dom/server';
import { hydrateRoot } from 'react-dom/client';
import { act } from '@testing-library/react';
import GuidePage from '../guide-page';

jest.mock('../../part-selection-modal', () => ({
  __esModule: true,
  default: () => null,
}));

/**
 * The frontend is compiled statically, so every guide page starts as
 * markup rendered without a URL and is then hydrated against one.
 *
 * `useSyncExternalStore`'s server snapshot is what stands in for the
 * URL until hydration, and it has to say "not known yet" rather than
 * "no guide". Those two answers render differently — one waits, the
 * other shows the guide list — and only a real hydration tells them
 * apart. `render()` skips the server pass entirely, so the whole
 * suite can miss this.
 */
describe('hydrating a guide page', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    jest.spyOn(console, 'error').mockImplementation(() => {});
  });

  it('does not flash the guide list before the URL is known', async () => {
    window.history.replaceState({}, '', '/guides/?guide=wall');
    const asked: string[] = [];
    global.fetch = jest.fn((url: string) => {
      asked.push(url);
      return Promise.resolve({
        ok: true,
        status: 200,
        json: () =>
          Promise.resolve(
            url.includes('/resolve')
              ? { steps: [], parts: [], refinements: [] }
              : {
                  guide_key: 'wall',
                  document: {
                    key: 'wall',
                    title: 'How do I make a wall?',
                    steps: [],
                    refinements: [],
                    roles: {},
                  },
                }
          ),
      });
    }) as unknown as typeof fetch;

    // The server pass has no URL at all, which is the point: it must
    // not commit to "there is no guide here".
    const markup = renderToString(<GuidePage />);
    expect(markup).not.toContain('Guided builds');

    const container = document.createElement('div');
    container.innerHTML = markup;
    document.body.appendChild(container);

    await act(async () => {
      hydrateRoot(container, <GuidePage />);
    });

    // The listing endpoint belongs to the other branch. Asking for it
    // means the guide list rendered, however briefly.
    expect(asked.filter((url) => url.endsWith('/api/guides'))).toEqual([]);
    expect(container.textContent).not.toContain('Guided builds');
  });
});
