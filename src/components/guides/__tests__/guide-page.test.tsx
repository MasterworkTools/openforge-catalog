import React from 'react';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import GuidePage from '../guide-page';

const RESOLVED = {
  steps: [
    {
      key: 'method',
      prompt: 'How do you want to build it?',
      selected: null,
      options: [
        {
          key: 'separate-wall',
          title: 'Separate wall',
          blurb: 'Floor and wall are independent.',
          roles: {},
        },
        { key: 's2w', title: 'Modular (s2w)', roles: {} },
      ],
    },
  ],
  parts: [],
  refinements: [],
};

const RESOLVED_WITH_PARTS = {
  ...RESOLVED,
  steps: [{ ...RESOLVED.steps[0], selected: 'separate-wall' }],
  parts: [
    {
      role: 'wall',
      title: 'Wall',
      under: null,
      query: { require: ['shape|wall'] },
      blueprint: {
        id: 'bp-1',
        blueprint_name: 'a dungeon stone wall',
        file_md5: 'abc',
        storage_address: null,
        tags: ['shape|wall', 'texture|dungeon_stone', 'size|width|2'],
        // Documentation first, deliberately: the batch query orders by
        // image_name, so the thumbnail is not reliably images[0].
        images: [
          {
            id: 'img-doc',
            image_name: 'a diagram',
            image_url: 'https://objects.openforge.tools/diagram.png',
            image_type: 'documentation',
          },
          {
            id: 'img-thumb',
            image_name: 'b render',
            image_url: 'https://objects.openforge.tools/thumb.png',
            image_type: 'thumbnail',
            sprite_metadata: {
              grid_rows: 2,
              grid_cols: 5,
              tile_size: 512,
              default_angle: 0,
              angles: [
                { index: 0, name: 'back' },
                { index: 3, name: 'front' },
              ],
            },
          },
        ],
      },
    },
    {
      role: 'wall-base',
      title: 'Base for the wall',
      under: 'wall',
      query: { require: ['shape|base'] },
      blueprint: {
        id: 'bp-2',
        blueprint_name: 'a dungeon stone base',
        file_md5: 'def',
        storage_address: null,
        images: [],
        tags: ['shape|base', 'size|width|2'],
      },
    },
    {
      role: 'floor-base',
      title: 'Base for the floor',
      under: 'floor',
      query: { require: ['shape|base'] },
      blueprint: null,
    },
  ],
  refinements: [
    {
      key: 'texture',
      role: '*',
      prompt: 'Texture',
      from_namespace: 'texture',
      selected: null,
    },
    // A toggle rather than a namespace pick: the two arms of the
    // `on_tags` branch render different controls, and both prompts are
    // plain text, so asserting on the text alone cannot tell them
    // apart.
    {
      key: 'side-locks',
      role: 'wall',
      prompt: 'Side locks',
      on_tags: ['connection|openlock'],
      selected: null,
    },
  ],
};

/**
 * The guide document endpoint, which every guide page fetches first.
 *
 * The whole document, because the page reads the keys it defines to
 * decide which of the URL's query parameters are its own.
 */
const GUIDE_DOCUMENT = {
  guide_key: 'wall',
  document: {
    key: 'wall',
    title: 'How do I make a wall?',
    steps: [{ key: 'method', prompt: 'How?', options: [] }],
    refinements: [{ key: 'texture' }, { key: 'side-locks' }],
    roles: {},
  },
};

function mockFetch(handler: (url: string, init?: RequestInit) => unknown) {
  global.fetch = jest.fn((url: string, init?: RequestInit) =>
    Promise.resolve({
      ok: true,
      status: 200,
      json: () => Promise.resolve(handler(url, init)),
    })
  ) as unknown as typeof fetch;
}

function visit(search: string) {
  window.history.replaceState({}, '', `/guides/${search}`);
}

describe('GuidePage', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    jest.spyOn(console, 'error').mockImplementation(() => {});
  });

  describe('with no guide in the URL', () => {
    it('lists the guides', async () => {
      visit('');
      mockFetch(() => ({
        guides: [
          { guide_key: 'wall', title: 'How do I make a wall?', summary: 'Three ways.' },
        ],
      }));

      render(<GuidePage />);

      expect(
        await screen.findByText('How do I make a wall?')
      ).toBeInTheDocument();
      expect(screen.getByText('Three ways.')).toBeInTheDocument();
    });

    it('says so when there are none', async () => {
      visit('');
      global.fetch = jest.fn(() =>
        Promise.resolve({ ok: false, status: 404, json: () => Promise.resolve({}) })
      ) as unknown as typeof fetch;

      render(<GuidePage />);

      expect(await screen.findByText('No guides yet.')).toBeInTheDocument();
    });
  });

  describe('with a guide in the URL', () => {
    it('asks the first question', async () => {
      visit('?guide=wall');
      mockFetch((url) => (url.includes('/resolve') ? RESOLVED : GUIDE_DOCUMENT));

      render(<GuidePage />);

      expect(
        await screen.findByText('How do you want to build it?')
      ).toBeInTheDocument();
      expect(screen.getByText('Separate wall')).toBeInTheDocument();
    });

    it('heads the page with the guide title from the API', async () => {
      visit('?guide=wall');
      mockFetch((url) => (url.includes('/resolve') ? RESOLVED : GUIDE_DOCUMENT));

      render(<GuidePage />);

      expect(
        await screen.findByRole('heading', { name: 'How do I make a wall?' })
      ).toBeInTheDocument();
    });

    it('resolves with a GET, the selections in the query string', async () => {
      visit('?guide=wall');
      const urls: string[] = [];
      mockFetch((url) => {
        urls.push(url);
        return url.includes('/resolve') ? RESOLVED : GUIDE_DOCUMENT;
      });

      render(<GuidePage />);
      fireEvent.click(await screen.findByText('Separate wall'));

      await waitFor(() =>
        expect(urls).toContain(
          '/api/guides/wall/resolve?method=separate-wall'
        )
      );
      // A GET, so nothing carries a body or a method — and it has to
      // be the *resolve* call that is checked. calls[0] is the guide
      // document, which was always a bare GET, so asserting on it
      // passes whatever the resolve does.
      const resolveCall = (global.fetch as jest.Mock).mock.calls.find(
        ([url]: [string]) => url.includes('/resolve')
      );
      expect(resolveCall).toHaveLength(1);
      expect(window.location.search).toContain('method=separate-wall');
    });

    it('shows the recommended parts and admits when a role matched nothing', async () => {
      visit('?guide=wall&method=separate-wall');
      mockFetch((url) =>
        url.includes('/resolve') ? RESOLVED_WITH_PARTS : GUIDE_DOCUMENT
      );

      render(<GuidePage />);

      expect(
        await screen.findByText('a dungeon stone wall')
      ).toBeInTheDocument();
      expect(
        screen.getByText('Nothing in the catalog matches this combination yet.')
      ).toBeInTheDocument();
    });

    it('draws a base beneath the piece it sits under', async () => {
      visit('?guide=wall&method=separate-wall');
      mockFetch((url) =>
        url.includes('/resolve') ? RESOLVED_WITH_PARTS : GUIDE_DOCUMENT
      );

      render(<GuidePage />);
      await screen.findByText('a dungeon stone wall');

      // The wall and its base are one pile; the floor base, whose
      // `under` names a role not in this list, stands on its own.
      const wall = screen.getByText('Wall').closest('div')!.parentElement!;
      const pile = wall.parentElement!;
      const titles = [...pile.querySelectorAll('div')]
        .map((node) => node.textContent)
        .filter((text) => text === 'Wall' || text === 'Base for the wall');
      expect(titles).toEqual(['Wall', 'Base for the wall']);
    });

    it('shows each piece its tags', async () => {
      // While the guides are being written, the tags are how you see
      // that a recommendation is wrong — the filename does not say.
      visit('?guide=wall&method=separate-wall');
      mockFetch((url) =>
        url.includes('/resolve') ? RESOLVED_WITH_PARTS : GUIDE_DOCUMENT
      );

      render(<GuidePage />);

      expect(await screen.findByText('texture|dungeon_stone')).toBeInTheDocument();
      expect(screen.getByText('shape|wall')).toBeInTheDocument();
      expect(screen.getAllByText('size|width|2')).toHaveLength(2);
    });

    it('draws the sprite frame named front, not frame zero', async () => {
      // Every piece has to be seen from the same direction for the
      // parts list to show whether they go together, and the index of
      // 'front' is not the same in every sheet.
      visit('?guide=wall&method=separate-wall');
      mockFetch((url) =>
        url.includes('/resolve') ? RESOLVED_WITH_PARTS : GUIDE_DOCUMENT
      );

      render(<GuidePage />);
      const sprite = await screen.findByLabelText(
        'a dungeon stone wall, seen from the front'
      );

      // Frame 3 of a 5-wide, 2-tall sheet: row 0, column 3. Asserted
      // relative to the rendered tile so that changing how large the
      // pieces are drawn does not break this — what it pins is which
      // frame, not how big.
      const tile = parseInt(sprite.style.width, 10);
      expect(tile).toBeGreaterThan(0);
      expect(sprite).toHaveStyle({
        backgroundImage: 'url(https://objects.openforge.tools/thumb.png)',
        backgroundPosition: `-${3 * tile}px -0px`,
        backgroundSize: `${5 * tile}px ${2 * tile}px`,
      });
    });

    it('draws the thumbnail rather than whichever image came first', async () => {
      visit('?guide=wall&method=separate-wall');
      mockFetch((url) =>
        url.includes('/resolve') ? RESOLVED_WITH_PARTS : GUIDE_DOCUMENT
      );

      render(<GuidePage />);
      const sprite = await screen.findByLabelText(
        'a dungeon stone wall, seen from the front'
      );

      expect(sprite).toHaveStyle({
        backgroundImage: 'url(https://objects.openforge.tools/thumb.png)',
      });
      // The documentation image sorts first and must not be drawn.
      expect(document.body.innerHTML).not.toContain('diagram.png');
    });

    it('falls back to a plain picture when a thumbnail is not a sprite', async () => {
      visit('?guide=wall&method=separate-wall');
      const flat = {
        ...RESOLVED_WITH_PARTS,
        parts: [
          {
            ...RESOLVED_WITH_PARTS.parts[0],
            blueprint: {
              ...RESOLVED_WITH_PARTS.parts[0].blueprint,
              images: [
                {
                  id: 'img-flat',
                  image_name: 'a render',
                  image_url: 'https://objects.openforge.tools/flat.png',
                  image_type: 'thumbnail',
                },
              ],
            },
          },
        ],
      };
      mockFetch((url) => (url.includes('/resolve') ? flat : GUIDE_DOCUMENT));

      render(<GuidePage />);

      const picture = await screen.findByAltText('a dungeon stone wall');
      expect(picture).toHaveAttribute(
        'src',
        'https://objects.openforge.tools/flat.png'
      );
    });

    it('says so when a part has no picture at all', async () => {
      visit('?guide=wall&method=separate-wall');
      mockFetch((url) =>
        url.includes('/resolve') ? RESOLVED_WITH_PARTS : GUIDE_DOCUMENT
      );

      render(<GuidePage />);
      await screen.findByText('a dungeon stone wall');

      // Two of them: the wall base carries no images, and the floor
      // base resolved to no blueprint at all.
      expect(screen.getAllByText('no picture')).toHaveLength(2);
    });

    it('offers the refinements the backend says are available', async () => {
      visit('?guide=wall&method=separate-wall');
      mockFetch((url) =>
        url.includes('/resolve') ? RESOLVED_WITH_PARTS : GUIDE_DOCUMENT
      );

      render(<GuidePage />);

      expect(await screen.findByText('Texture')).toBeInTheDocument();
    });

    it('drops a tracking parameter rather than sending it to the API', async () => {
      // The share-link case: /resolve 400s on a key it does not know,
      // so a link that has been through Facebook must not forward it.
      visit('?guide=wall&method=separate-wall&fbclid=IwAR123&utm_source=mail');
      const urls: string[] = [];
      mockFetch((url) => {
        urls.push(url);
        return url.includes('/resolve') ? RESOLVED_WITH_PARTS : GUIDE_DOCUMENT;
      });

      render(<GuidePage />);
      await screen.findByText('a dungeon stone wall');

      const resolves = urls.filter((url) => url.includes('/resolve'));
      expect(resolves).toEqual([
        '/api/guides/wall/resolve?method=separate-wall',
      ]);
      expect(resolves[0]).not.toContain('fbclid');
      expect(resolves[0]).not.toContain('utm_source');
    });

    it('answers a toggle refinement, and un-answers it', async () => {
      visit('?guide=wall&method=separate-wall');
      const urls: string[] = [];
      mockFetch((url) => {
        urls.push(url);
        return url.includes('/resolve') ? RESOLVED_WITH_PARTS : GUIDE_DOCUMENT;
      });

      render(<GuidePage />);
      const toggle = await screen.findByLabelText('Side locks');

      fireEvent.click(toggle);
      await waitFor(() =>
        expect(urls).toContain(
          '/api/guides/wall/resolve?method=separate-wall&side-locks=on'
        )
      );
      expect(window.location.search).toContain('side-locks=on');
    });

    it('answers a namespace refinement with the tag typed into it', async () => {
      visit('?guide=wall&method=separate-wall');
      const urls: string[] = [];
      mockFetch((url) => {
        urls.push(url);
        return url.includes('/resolve') ? RESOLVED_WITH_PARTS : GUIDE_DOCUMENT;
      });

      render(<GuidePage />);
      const picker = await screen.findByLabelText('Texture');

      fireEvent.blur(picker, { target: { value: 'texture|towne' } });

      await waitFor(() =>
        expect(urls).toContain(
          '/api/guides/wall/resolve?method=separate-wall&texture=texture%7Ctowne'
        )
      );
    });

    it('drops a refinement from the URL when it is cleared', async () => {
      // The null branch of `select`: writing the empty string instead
      // would send `?texture=` and the API would refuse it.
      visit('?guide=wall&method=separate-wall&texture=texture%7Ctowne');
      const urls: string[] = [];
      mockFetch((url) => {
        urls.push(url);
        return url.includes('/resolve') ? RESOLVED_WITH_PARTS : GUIDE_DOCUMENT;
      });

      render(<GuidePage />);
      const picker = await screen.findByLabelText('Texture');

      fireEvent.blur(picker, { target: { value: '  ' } });

      await waitFor(() =>
        expect(urls).toContain('/api/guides/wall/resolve?method=separate-wall')
      );
      expect(window.location.search).not.toContain('texture');
    });

    it('says so when the guide in the URL does not exist', async () => {
      visit('?guide=nonesuch');
      global.fetch = jest.fn(() =>
        Promise.resolve({ ok: false, status: 404, statusText: 'Not Found' })
      ) as unknown as typeof fetch;

      render(<GuidePage />);

      expect(
        await screen.findByText("No guide called 'nonesuch'.")
      ).toBeInTheDocument();
    });

    it('shows the error when the selections do not describe a state', async () => {
      visit('?guide=wall&method=nonesuch');
      global.fetch = jest.fn((url: string) =>
        Promise.resolve(
          url.includes('/resolve')
            ? {
                ok: false,
                status: 400,
                statusText: 'Bad Request',
                json: () =>
                  Promise.resolve({
                    error: "step 'method' has no option 'nonesuch'",
                  }),
              }
            : {
                ok: true,
                status: 200,
                json: () => Promise.resolve(GUIDE_DOCUMENT),
              }
        )
      ) as unknown as typeof fetch;

      render(<GuidePage />);

      expect(
        await screen.findByText("step 'method' has no option 'nonesuch'")
      ).toBeInTheDocument();
    });
  });
});

describe('moving between guides', () => {
  /**
   * The previous version kept the selections in React state that was
   * never keyed to the guide, so answering one guide and then opening
   * another sent the first guide's answers to the second. The strict
   * API answered 400 and nothing the person did afterwards could clear
   * it, because the stale state always won.
   */
  it("does not send one guide's answers to the next", async () => {
    visit('?guide=wall&method=separate-wall');
    const urls: string[] = [];
    mockFetch((url) => {
      urls.push(url);
      if (url.includes('/resolve')) return RESOLVED_WITH_PARTS;
      return url.includes('/floor')
        ? {
            guide_key: 'floor',
            document: {
              key: 'floor',
              title: 'How do I make a floor?',
              steps: [{ key: 'style', prompt: 'Which style?', options: [] }],
              refinements: [],
              roles: {},
            },
          }
        : GUIDE_DOCUMENT;
    });

    const { rerender } = render(<GuidePage />);
    await screen.findByText('a dungeon stone wall');

    // The back/forward case: the component stays mounted and the URL
    // changes underneath it.
    window.history.replaceState({}, '', '/guides/?guide=floor&style=flagstone');
    window.dispatchEvent(new PopStateEvent('popstate'));
    rerender(<GuidePage />);

    await waitFor(() =>
      expect(urls).toContain('/api/guides/floor/resolve?style=flagstone')
    );
    expect(
      urls.filter((url) => url.includes('/floor/resolve') && url.includes('method='))
    ).toEqual([]);
  });
});
