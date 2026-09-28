import React from 'react';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom';
import TabbedInterface from '../tabbed-interface';

/**
 * The tabs, and which of them costs a request.
 *
 * `Guided Builds` took the `Blueprints` slot, so this covers both that
 * the new one is there and that the old one is gone — a test for the
 * first alone passes while both exist.
 */

// The guides tab now renders `GuidePage`, which reaches
// `part-selection-modal` -> `blueprint-container` and a dependency jest
// cannot parse. `guide-page.test.tsx` mocks the same boundary for the
// same reason. Without it this suite fails to load, which `Tests: N
// passed` does not show — only the suite count does.
jest.mock('../part-selection-modal', () => ({
  __esModule: true,
  default: () => null,
}));
jest.mock('../tab-part-search', () => ({
  __esModule: true,
  default: () => <div data-testid="part-search" />,
}));
jest.mock('../tab-admin', () => ({
  __esModule: true,
  default: () => <div data-testid="admin" />,
}));
jest.mock('@/contexts/admin-context', () => ({
  useAdminContext: () => ({ state: { isAuthenticated: false } }),
}));
jest.mock('@/utils/app-config', () => ({
  loadAppConfig: () => Promise.resolve({}),
}));

function noGuides() {
  const fetch = jest.fn((): Promise<unknown> =>
    Promise.resolve({
      ok: false,
      status: 404,
      json: () => Promise.resolve({ guides: [] }),
    })
  );
  global.fetch = fetch as unknown as typeof global.fetch;
  return fetch;
}

function guideRequests(fetch: jest.Mock): string[] {
  return fetch.mock.calls
    .map((call) => String(call[0]))
    .filter((url) => url.includes('/api/guides'));
}

describe('TabbedInterface', () => {
  it('offers Guided Builds where Blueprints used to be', async () => {
    noGuides();

    render(<TabbedInterface />);

    expect(
      screen.getByRole('button', { name: 'Guided Builds' })
    ).toBeInTheDocument();
    // The other half: a test for the new tab alone passes while both are
    // there, and the point of this change was that one replaced the other.
    expect(
      screen.queryByRole('button', { name: 'Blueprints' })
    ).not.toBeInTheDocument();
  });

  it('does not ask for the guides until the tab is opened', async () => {
    // A hidden component still runs its effects. Mounting the entry page
    // beside the others would spend a Lambda invocation on /api/guides
    // for every visitor who never opens this tab, which on a 128MB
    // function with a Patreon budget is the kind of cost that only shows
    // up on the bill.
    const fetch = noGuides();

    render(<TabbedInterface />);

    expect(guideRequests(fetch)).toHaveLength(0);

    fireEvent.click(screen.getByRole('button', { name: 'Guided Builds' }));

    await waitFor(() => expect(guideRequests(fetch)).toHaveLength(1));
    expect(
      await screen.findByRole('heading', { name: 'Guided builds' })
    ).toBeInTheDocument();
  });

  it('does not nest a second landmark inside the page', async () => {
    // The entry page is also the whole of `/guides`, where it needs a
    // `main`. As a tab panel it is inside `MainContentWrapper`'s, and
    // `main` forbids a `main` ancestor. Counted on the document rather
    // than queried within the render result, because `getByRole('main')`
    // would happily find the inner one and report success.
    noGuides();

    render(<TabbedInterface />);
    fireEvent.click(screen.getByRole('button', { name: 'Guided Builds' }));
    await screen.findByRole('heading', { name: 'Guided builds' });

    expect(document.querySelectorAll('main')).toHaveLength(0);
  });

  it('keeps Part Search mounted across a trip to another tab', async () => {
    // The guides tab is conditional so a hidden component does not spend
    // a Lambda invocation. Its neighbours must NOT be: `TabPartSearch`
    // owns the `TagProvider` and `BlueprintProvider`, so unmounting it
    // throws away the visitor's tag selection and results every time
    // they look at the guides and come back. Only a `style` prop says
    // otherwise today, and a style prop fails no test — so this asserts
    // on the identity of the node, not on its visibility.
    noGuides();

    render(<TabbedInterface />);
    const search = screen.getByTestId('part-search');
    const generator = screen.getByTitle('Base Generator');

    fireEvent.click(screen.getByRole('button', { name: 'Guided Builds' }));
    await screen.findByRole('heading', { name: 'Guided builds' });
    fireEvent.click(screen.getByRole('button', { name: 'Part Search' }));

    expect(screen.getByTestId('part-search')).toBe(search);
    // And the Base Generator, where the loss is larger still: remounting
    // that iframe reloads an external application and discards a base
    // somebody was part-way through designing. It is also the sibling
    // with a written argument for breaking it — the comment beside the
    // guides tab says a hidden component costing a request is why that
    // one is conditional, which applies more strongly to a document
    // fetch than to anything else here. Pinning only one neighbour is
    // the same mistake this test was added to fix.
    expect(screen.getByTitle('Base Generator')).toBe(generator);
  });

  it('starts on Part Search', async () => {
    noGuides();

    render(<TabbedInterface />);

    expect(screen.getByTestId('part-search')).toBeInTheDocument();
    expect(
      screen.queryByRole('heading', { name: 'Guided builds' })
    ).not.toBeInTheDocument();
  });
});
