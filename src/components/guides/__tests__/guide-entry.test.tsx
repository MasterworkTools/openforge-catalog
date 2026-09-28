import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import GuideEntry from '../guide-entry';

/**
 * The entry page's cards.
 *
 * The three states the old list had — heading, none yet, could not ask —
 * are covered against `GuidePage` in `guide-page.test.tsx` and pass
 * unchanged against this component, which is exactly why they prove
 * nothing about a card. Everything here is about the picture.
 */

function served(guides: unknown[]) {
  global.fetch = jest.fn(() =>
    Promise.resolve({
      ok: true,
      status: 200,
      json: () => Promise.resolve({ guides }),
    })
  ) as unknown as typeof fetch;
}

function occurrences(haystack: string, needle: string): number {
  return haystack.split(needle).length - 1;
}

const WALL = {
  guide_key: 'wall',
  title: 'How do I make a wall?',
  summary: 'Three ways.',
  hero_image: 'https://objects.openforge.tools/guides/wall.webp',
};

describe('GuideEntry', () => {
  afterEach(() => {
    jest.restoreAllMocks();
  });

  it('draws the illustration the guide carries', async () => {
    served([WALL]);

    render(<GuideEntry />);

    const image = await screen.findByRole('presentation');
    expect(image).toHaveAttribute('src', WALL.hero_image);
  });

  it('names the card once, not twice', async () => {
    // The whole card is one link, so its accessible name is its
    // contents. An alt of the title makes a screen reader announce
    // "How do I make a wall?" twice in a row for one card. The image is
    // decorative *because* the heading beside it names the thing — which
    // is only true while the heading is there, so this asserts both.
    served([WALL]);

    render(<GuideEntry />);

    const link = await screen.findByRole('link');
    // The name is the card's whole text — title then summary — so the
    // claim is that the title appears in it once. With `alt={title}` it
    // appears twice, which is the mutant this kills.
    const name = link.getAttribute('aria-label') ?? link.textContent ?? '';
    expect(occurrences(name, WALL.title)).toBe(1);
    expect(
      screen.getByRole('heading', { name: WALL.title, level: 2 })
    ).toBeInTheDocument();
  });

  it('is a link over the whole card, not just the title', async () => {
    served([WALL]);

    render(<GuideEntry />);

    const link = await screen.findByRole('link');
    expect(link).toHaveAttribute('href', '/guides?guide=wall');
    // The picture and the words are both inside it. A card whose title
    // alone is clickable has a large dead area that looks clickable.
    expect(link).toContainElement(screen.getByRole('presentation'));
    expect(link).toContainElement(screen.getByText('Three ways.'));
  });

  it('shows a frame rather than a broken image when the file is missing', async () => {
    // The ordinary state while a guide is being authored: the document
    // carries the URL and uploading the file is a separate step. A
    // browser's broken-image glyph reads as a bug in the page.
    served([WALL]);

    render(<GuideEntry />);
    const image = await screen.findByRole('presentation');

    fireEvent.error(image);

    await waitFor(() =>
      expect(screen.queryByRole('presentation')).not.toBeInTheDocument()
    );
    // And the card survives it — the title is still there to click.
    expect(screen.getByRole('link')).toContainElement(
      screen.getByRole('heading', { name: WALL.title, level: 2 })
    );
  });

  it('carries a guide that has no illustration at all', async () => {
    // `image` is nullable in earnest: it is not a required field, so a
    // guide is authorable without one and this must not throw.
    served([{ ...WALL, hero_image: null }]);

    render(<GuideEntry />);

    expect(
      await screen.findByRole('heading', { name: WALL.title, level: 2 })
    ).toBeInTheDocument();
    expect(screen.queryByRole('presentation')).not.toBeInTheDocument();
  });

  it('gives every guide its own card', async () => {
    served([WALL, { ...WALL, guide_key: 'floor', title: 'A floor' }]);

    render(<GuideEntry />);

    await screen.findByRole('heading', { name: 'A floor', level: 2 });
    expect(screen.getAllByRole('link')).toHaveLength(2);
    expect(screen.getAllByRole('listitem')).toHaveLength(2);
  });
});
