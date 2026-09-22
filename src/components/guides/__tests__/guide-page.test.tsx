import React from 'react';
import { render, screen, waitFor, fireEvent, act } from '@testing-library/react';
import GuidePage from '../guide-page';

/**
 * The part-selection modal is the catalog's own, and it drags in the
 * tag and blueprint providers plus an ESM-only dependency. What this
 * page is responsible for is opening it with the predicate that
 * narrowed the part down, so that is what is asserted.
 */
const downloaded: string[][] = [];
jest.mock('@/utils/blueprint-utils', () => ({
  ...jest.requireActual('@/utils/blueprint-utils'),
  downloadFiles: (urls: string[]) => {
    downloaded.push(urls);
  },
}));

const modalProps: Record<string, unknown>[] = [];
jest.mock('../../part-selection-modal', () => ({
  __esModule: true,
  default: (props: Record<string, unknown>) => {
    modalProps.push(props);
    return props.isOpen ? <div data-testid="part-modal" /> : null;
  },
}));

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
      query: {
        require: ['shape|wall'],
        deny: [],
        accept: [],
        deny_children: ['component|wall'],
        allow: ['shape|square'],
      },
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
    modalProps.length = 0;
    downloaded.length = 0;
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
      // The other half of the distinction: an empty collection is a
      // 404 by house convention, so it must not read as a failure.
      expect(
        screen.queryByText('Could not load the guides.')
      ).not.toBeInTheDocument();
    });

    it('distinguishes "could not ask" from "none yet"', async () => {
      // Both arms render an empty list, so without this the `failed`
      // flag can be deleted and every other test still passes.
      visit('');
      global.fetch = jest.fn(() =>
        Promise.resolve({
          ok: false,
          status: 500,
          statusText: 'Internal Server Error',
          json: () => Promise.resolve({}),
        })
      ) as unknown as typeof fetch;

      render(<GuidePage />);

      expect(
        await screen.findByText('Could not load the guides.')
      ).toBeInTheDocument();
      expect(screen.queryByText('No guides yet.')).not.toBeInTheDocument();
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

    it('answers a question without faking browser navigation', async () => {
      // The page has to announce its own URL writes, because
      // replaceState fires nothing. Announcing them as `popstate` is
      // what the part-selection modal listens for: BlueprintContainer
      // reloads the page on popstate when a blueprint is selected and
      // the URL has no blueprint_id, so every answer clicked with that
      // modal open would reload the page out from under it.
      visit('?guide=wall');
      mockFetch((url) => (url.includes('/resolve') ? RESOLVED : GUIDE_DOCUMENT));
      const popstates: Event[] = [];
      const record = (e: Event) => popstates.push(e);
      window.addEventListener('popstate', record);

      try {
        render(<GuidePage />);
        fireEvent.click(await screen.findByText('Separate wall'));
        await waitFor(() =>
          expect(window.location.search).toContain('method=separate-wall')
        );

        expect(popstates).toEqual([]);
      } finally {
        window.removeEventListener('popstate', record);
      }
    });

    it('shows which option is the chosen one', async () => {
      // Raised in both review rounds: forcing `aria-pressed` to false
      // and dropping the selected styling left the suite green, so
      // nothing held the page to showing an answer as answered.
      visit('?guide=wall&method=separate-wall');
      mockFetch((url) =>
        url.includes('/resolve') ? RESOLVED_WITH_PARTS : GUIDE_DOCUMENT
      );

      render(<GuidePage />);

      const chosen = await screen.findByRole('button', { name: /Separate wall/ });
      expect(chosen).toHaveAttribute('aria-pressed', 'true');
      expect(
        screen.getByRole('button', { name: /Modular \(s2w\)/ })
      ).toHaveAttribute('aria-pressed', 'false');
    });

    it('offers one download per part that actually resolved', async () => {
      // Three parts, one of which matched nothing. The regression this
      // pins is the null part contributing
      // `/api/blueprints/undefined/download` to the list — which is a
      // 404 the person only discovers after clicking.
      visit('?guide=wall&method=separate-wall');
      mockFetch((url) =>
        url.includes('/resolve') ? RESOLVED_WITH_PARTS : GUIDE_DOCUMENT
      );

      render(<GuidePage />);
      fireEvent.click(await screen.findByText('Download all 2 files'));

      expect(downloaded).toEqual([
        ['/api/blueprints/bp-1/download', '/api/blueprints/bp-2/download'],
      ]);
    });

    it('offers no download button when nothing resolved', async () => {
      visit('?guide=wall&method=separate-wall');
      const nothing = {
        ...RESOLVED_WITH_PARTS,
        parts: RESOLVED_WITH_PARTS.parts.map((part) => ({
          ...part,
          blueprint: null,
        })),
      };
      mockFetch((url) => (url.includes('/resolve') ? nothing : GUIDE_DOCUMENT));

      render(<GuidePage />);
      await screen.findByText('Wall');

      expect(
        screen.queryByRole('button', { name: /^Download/ })
      ).not.toBeInTheDocument();
    });

    it('shows a refinement its current answer', async () => {
      // The answer lives in the URL, so a shared link has to arrive
      // with the box filled in. `defaultValue` is what does that, and
      // an uncontrolled input reads empty without it whatever the
      // refinement says.
      visit('?guide=wall&method=separate-wall&texture=texture|dungeon_stone');
      mockFetch((url) =>
        url.includes('/resolve')
          ? {
              ...RESOLVED_WITH_PARTS,
              refinements: RESOLVED_WITH_PARTS.refinements.map((r) =>
                r.key === 'texture'
                  ? { ...r, selected: 'texture|dungeon_stone' }
                  : r
              ),
            }
          : GUIDE_DOCUMENT
      );

      render(<GuidePage />);

      const box = (await screen.findByPlaceholderText(
        'texture|...'
      )) as HTMLInputElement;
      expect(box.value).toBe('texture|dungeon_stone');
    });

    it('lets the newest answer win when an older one lands last', async () => {
      // Every click re-fires the resolve effect, and the network does
      // not promise to answer in order. Without the `current` guard
      // the first, slower answer arrives last and overwrites the one
      // the person is actually looking at — so the page shows the
      // parts for a method they already changed their mind about.
      visit('?guide=wall');
      const pending: ((value: unknown) => void)[] = [];
      let resolves = 0;
      global.fetch = jest.fn((url: string) => {
        if (!url.includes('/resolve')) {
          return Promise.resolve({
            ok: true,
            status: 200,
            json: () => Promise.resolve(GUIDE_DOCUMENT),
          });
        }
        resolves += 1;
        // The first one lands, so the questions render and can be
        // clicked. The two after it are held open by hand.
        const body =
          resolves === 1
            ? Promise.resolve(RESOLVED)
            : new Promise((resolve) => pending.push(resolve));
        return Promise.resolve({ ok: true, status: 200, json: () => body });
      }) as unknown as typeof fetch;

      render(<GuidePage />);
      fireEvent.click(await screen.findByText('Separate wall'));
      await waitFor(() => expect(pending).toHaveLength(1));
      fireEvent.click(screen.getByText('Modular (s2w)'));
      await waitFor(() => expect(pending).toHaveLength(2));

      // Newest first, then the stale one — the order that breaks it.
      pending[pending.length - 1](RESOLVED_WITH_PARTS);
      await screen.findByText('a dungeon stone wall');
      pending[pending.length - 2]({
        ...RESOLVED_WITH_PARTS,
        parts: [
          {
            ...RESOLVED_WITH_PARTS.parts[0],
            blueprint: {
              ...RESOLVED_WITH_PARTS.parts[0].blueprint,
              blueprint_name: 'the wall for the method they left',
            },
          },
        ],
      });

      // The stale answer has to be given its chance to land before
      // this is asserted, or the assertion passes on timing rather
      // than on the guard.
      await act(async () => {
        await Promise.resolve();
        await Promise.resolve();
      });

      expect(screen.getByText('a dungeon stone wall')).toBeInTheDocument();
      expect(
        screen.queryByText('the wall for the method they left')
      ).not.toBeInTheDocument();
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

describe('inspecting a part', () => {
  it('opens the tag search seeded with what narrowed that part down', async () => {
    visit('?guide=wall&method=separate-wall');
    mockFetch((url) =>
      url.includes('/resolve') ? RESOLVED_WITH_PARTS : GUIDE_DOCUMENT
    );

    render(<GuidePage />);
    fireEvent.click(await screen.findByLabelText(/a dungeon stone wall, seen/));

    expect(await screen.findByTestId('part-modal')).toBeInTheDocument();
    const opened = modalProps[modalProps.length - 1];
    expect(opened.partName).toBe('Wall (wall)');
    // Every term the search can act on, including the two the tag
    // tree cannot edit: the modal has to open on the set the guide
    // resolved against, not a wider one.
    //
    // `accept` is absent on purpose. The search has no subtree
    // predicate, so passing one would be seeding the modal with a
    // term that is silently discarded — and a discarded restriction
    // is a wider set, which is the failure this assertion exists to
    // catch.
    expect(opened.configValues).toEqual({
      require: [{ tag: 'shape|wall' }],
      deny: [],
      deny_children: [{ tag: 'component|wall' }],
      allow: [{ tag: 'shape|square' }],
    });
    expect(opened.configValues).not.toHaveProperty('accept');
  });

  it('is closed until a part is clicked', async () => {
    visit('?guide=wall&method=separate-wall');
    mockFetch((url) =>
      url.includes('/resolve') ? RESOLVED_WITH_PARTS : GUIDE_DOCUMENT
    );

    render(<GuidePage />);
    await screen.findByText('a dungeon stone wall');

    expect(screen.queryByTestId('part-modal')).not.toBeInTheDocument();
  });
});
