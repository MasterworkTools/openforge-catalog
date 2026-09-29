import React from 'react';
import { render } from '@testing-library/react';
import '@testing-library/jest-dom';
import Guides from '../page';

jest.mock('@/components/guides/guide-page', () => ({
  __esModule: true,
  default: () => <div data-testid="guide-page" />,
}));

/**
 * The route half of both route-versus-panel fixes.
 *
 * `GuidePage` is the whole of `/guides` and also the Guided Builds tab
 * panel, so it declares neither a landmark nor a viewport height — the
 * container knows which it is and the component does not. That makes
 * this wrapper load-bearing in a way nothing observed: deleting it left
 * the entire suite green while `/guides` lost its `main` and its height
 * at once, which is the pair of defects that took three rounds to fix.
 */
describe('/guides', () => {
  it('supplies the landmark the component does not declare', () => {
    const { container } = render(<Guides />);

    const main = container.querySelector('main');
    expect(main).toBeInTheDocument();
    expect(main).toContainElement(container.querySelector('[data-testid="guide-page"]'));
  });

  it('supplies the viewport height the component does not claim', () => {
    // A class assertion for the same reason as `lg:h-full` in
    // `guide-page.test.tsx`: jsdom resolves no media query, so the class
    // string is the only observable carrier. Inside the tab this height
    // must *not* be applied — the pane is already sized — which is why
    // it lives here and not in the component.
    const { container } = render(<Guides />);

    expect(container.querySelector('main')?.className).toContain('lg:h-screen');
  });
});
