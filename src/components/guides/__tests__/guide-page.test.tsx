import React from 'react';
import {
  render,
  screen,
  waitFor,
  fireEvent,
  act,
  within,
} from '@testing-library/react';
import GuidePage from '../guide-page';
import type { ResolvedGuide } from '@/services/guide-service';

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

const RESOLVED: ResolvedGuide = {
  steps: [
    {
      key: 'method',
      prompt: 'How do you want to build it?',
      selected: null,
      // `resolve()` sets these on every question it returns, so the
      // fixture does too — the annotation above is what makes that a
      // compile error rather than a silent divergence from the API.
      unavailable: [],
      because: {},
      recommended: null,
      options: [
        {
          key: 'separate-wall',
          title: 'Separate wall',
          blurb:
            'Floor and wall are independent. Others doing this ' +
            'include Printable Scenery, and Printable Scenery again.',
          links: { 'Printable Scenery': 'https://www.printablescenery.com' },
          roles: {},
        },
        {
          key: 's2w',
          title: 'Modular (s2w)',
          blurb: 'Everything prints separately and stacks.',
          roles: {},
        },
      ],
    },
  ],
  parts: [],
  refinements: [],
};

const EMPTY_RESOLVED: ResolvedGuide = { steps: [], parts: [], refinements: [] };

const RESOLVED_WITH_PARTS: ResolvedGuide = {
  ...RESOLVED,
  steps: [{ ...RESOLVED.steps[0], selected: 'separate-wall' }],
  parts: [
    {
      role: 'wall',
      title: 'Wall',
      under: null,
      query: {
        require: ['shape|wall', 'texture|dungeon_stone'],
        deny: [],
        accept: [],
        deny_children: ['component|wall'],
        allow: ['shape|square'],
      },
      relaxable: ['texture|dungeon_stone'],
      pinned: false,
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
      relaxable: [],
      pinned: false,
      blueprint: {
        id: 'bp-2',
        blueprint_name: 'a dungeon stone base',
        file_md5: 'def',
        storage_address: null,
        // Deliberately a different frame order from the wall's sheet:
        // 'right' is index 1 here and index 2 there. The parts stay in
        // step by angle *name*, so a sheet that orders its frames
        // differently still faces the same way — and a version that
        // shared an index instead would put these two out of step.
        images: [
          {
            id: 'img-base',
            image_name: 'base render',
            image_url: 'https://objects.openforge.tools/base.png',
            image_type: 'thumbnail',
            sprite_metadata: {
              grid_rows: 1,
              grid_cols: 3,
              tile_size: 512,
              default_angle: 0,
              angles: [
                { index: 0, name: 'front' },
                { index: 1, name: 'right' },
                { index: 2, name: 'top' },
              ],
            },
          },
        ],
        tags: ['shape|base', 'size|width|2'],
      },
    },
    {
      role: 'floor-base',
      title: 'Base for the floor',
      under: 'floor',
      query: { require: ['shape|base'] },
      relaxable: [],
      pinned: false,
      blueprint: null,
    },
  ],
  refinements: [
    {
      key: 'texture',
      role: '*',
      prompt: 'Texture',
      from_namespace: 'texture',
      unavailable: [],
      because: {},
      recommended: null,
      selected: null,
    },
    // A closed list, which is drawn as buttons rather than a text box.
    {
      key: 'floor-texture',
      role: 'floor',
      prompt: 'Floor texture',
      from_namespace: 'texture',
      choices: [
        { tag: 'texture|dungeon_stone', title: 'Dungeon stone' },
        // A blurb, so the column beside the list has something to
        // drop when this answer is not on offer.
        { tag: 'texture|cave', blurb: 'Lumpy and irregular.' },
      ],
      unavailable: [],
      because: {},
      recommended: null,
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
      unavailable: [],
      because: {},
      recommended: null,
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
    refinements: [
      { key: 'texture' },
      { key: 'floor-texture' },
      { key: 'side-locks' },
    ],
    // The roles this guide builds. They are also the pin keys the page
    // will forward — `part.wall` — so an empty map here would make a
    // pinned part look like somebody else's query parameter.
    roles: { wall: {}, floor: {}, 'wall-base': {}, 'floor-base': {} },
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
    // The wall fixture's sheet deliberately lacks most of the ring, so
    // the turntable tests exercise the missing-angle fallback and
    // `GuideSprite` says so. Captured rather than printed, and the one
    // test the gap is *about* asserts it below.
    jest.spyOn(console, 'warn').mockImplementation(() => {});
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
        await screen.findByRole('heading', {
          name: 'How do you want to build it?',
        })
      ).toBeInTheDocument();
      expect(
        screen.getByRole('button', { name: /Separate wall/ })
      ).toBeInTheDocument();
      // The same options are explained in the other column, which is
      // where the difference between them actually lives.
      expect(screen.getByRole('heading', { name: 'What these mean' })).toBeInTheDocument();
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
      fireEvent.click(
        await screen.findByRole('button', { name: /Separate wall/ })
      );

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
        fireEvent.click(
          await screen.findByRole('button', { name: /Separate wall/ })
        );
        await waitFor(() =>
          expect(window.location.search).toContain('method=separate-wall')
        );

        expect(popstates).toEqual([]);
      } finally {
        window.removeEventListener('popstate', record);
      }
    });

    it('offers a way out of a resolve failure, and it drops the answers', async () => {
      // The whole page renders behind `resolved`, so on a first-load
      // failure this link is the only control there is. It shipped
      // uncovered, which is how its second arm stayed broken.
      visit('?guide=wall&method=nonesuch');
      global.fetch = jest.fn((url: string) =>
        Promise.resolve(
          url.includes('/resolve')
            ? {
                ok: false,
                status: 400,
                statusText: 'Bad Request',
                json: () =>
                  Promise.resolve({ error: "step 'method' has no option" }),
              }
            : {
                ok: true,
                status: 200,
                json: () => Promise.resolve(GUIDE_DOCUMENT),
              }
        )
      ) as unknown as typeof fetch;

      render(<GuidePage />);

      const out = await screen.findByRole('link', {
        name: 'Start this guide over',
      });
      // Back to this guide with no answers — not to the URL that just
      // failed.
      expect(out).toHaveAttribute('href', '?guide=wall');
    });

    it('sends you to the list when the guide itself is the thing missing', async () => {
      // The other arm of the same error. Starting `nosuch` over reloads
      // the identical 404, and `/guides` has no nav, so that link was
      // the only control on the page and it pointed at the failure.
      visit('?guide=nosuch');
      global.fetch = jest.fn(() =>
        Promise.resolve({ ok: false, status: 404, statusText: 'Not Found' })
      ) as unknown as typeof fetch;

      render(<GuidePage />);

      expect(
        await screen.findByText("No guide called 'nosuch'.")
      ).toBeInTheDocument();
      expect(screen.getByRole('link', { name: 'All guides' })).toHaveAttribute(
        'href',
        './'
      );
      expect(
        screen.queryByRole('link', { name: 'Start this guide over' })
      ).toBeNull();
    });

    it('says which of your own answers broke the build, not only the others', async () => {
      // The reason for the answer in force used to be computed and then
      // dropped, so the page held the diagnosis and showed every line
      // except that one.
      visit('?guide=wall&method=separate-wall&floor-texture=texture|cave');
      global.fetch = jest.fn((url: string) => {
        const body = url.includes('/availability')
          ? {
              unavailable: { 'floor-texture': ['texture|cave'] },
              because: {
                'floor-texture': {
                  'texture|cave': {
                    part: 'Floor',
                    question: 'method',
                    prompt: 'How do you want to build it?',
                  },
                },
              },
              options: {},
            }
          : url.includes('/resolve')
            ? {
                ...RESOLVED_WITH_PARTS,
                refinements: RESOLVED_WITH_PARTS.refinements.map((r) =>
                  r.key === 'floor-texture'
                    ? { ...r, selected: 'texture|cave' }
                    : r
                ),
              }
            : GUIDE_DOCUMENT;
        return Promise.resolve({
          ok: true,
          status: 200,
          json: () => Promise.resolve(body),
        });
      }) as unknown as typeof fetch;

      render(<GuidePage />);

      // Folded to its answer, with the reason beside it rather than a
      // tidy label and silence.
      await waitFor(() =>
        expect(document.body.textContent).toContain('Leaves no Floor')
      );
      // And it names the question responsible, rather than only the
      // answers that happen to be absent.
      expect(document.body.textContent).toContain(
        'it is your "How do you want to build it?" answer'
      );
    });

    it('folds grouped questions into one section and leaves others alone', async () => {
      // `wall.yaml` groups four refinements under two headings, and
      // nothing exercised the merge. A group shows its own heading once
      // with every question's prompt inside; an ungrouped question is
      // its own heading and must not repeat the prompt underneath.
      visit('?guide=wall&method=separate-wall');
      mockFetch((url) =>
        url.includes('/resolve')
          ? {
              ...RESOLVED_WITH_PARTS,
              refinements: [
                {
                  key: 'base-clips',
                  role: '*',
                  prompt: 'Which clip',
                  group: 'How do the pieces clip together?',
                  from_namespace: 'connection',
                  unavailable: [],
                  because: {},
                  recommended: null,
                  selected: null,
                },
                {
                  key: 'wall-clips',
                  role: 'wall',
                  prompt: 'Clips on the wall',
                  group: 'How do the pieces clip together?',
                  from_namespace: 'connection',
                  unavailable: [],
                  because: {},
                  recommended: null,
                  selected: null,
                },
                // A *second* group, immediately after the first, which
                // is the shape `wall.yaml` actually ships — `pegs`
                // under "Other options" follows three clip questions.
                // With only one group, dropping the name comparison
                // merges everything into it and nothing notices.
                {
                  key: 'pegs',
                  role: '*',
                  prompt: 'Peg holes',
                  group: 'Other options',
                  from_namespace: 'connection',
                  unavailable: [],
                  because: {},
                  recommended: null,
                  selected: null,
                },
                {
                  key: 'texture',
                  role: '*',
                  prompt: 'Texture',
                  from_namespace: 'texture',
                  unavailable: [],
                  because: {},
                  recommended: null,
                  selected: null,
                },
              ],
            }
          : GUIDE_DOCUMENT
      );

      render(<GuidePage />);

      // One shared heading for the two that belong together...
      expect(
        await screen.findByText('How do the pieces clip together?')
      ).toBeInTheDocument();
      // ...and the next group keeps its own heading rather than being
      // swallowed by the one before it.
      expect(screen.getByText('Other options')).toBeInTheDocument();
      expect(screen.getByText('Peg holes')).toBeInTheDocument();
      // ...with both prompts inside it, which a lone question omits.
      expect(screen.getByText('Which clip')).toBeInTheDocument();
      expect(screen.getByText('Clips on the wall')).toBeInTheDocument();
      // The ungrouped one is its own heading and says its prompt once.
      expect(screen.getAllByText('Texture')).toHaveLength(1);
    });

    it('names the combination in the free-text box, not `undefined`', async () => {
      // A combination refinement has no `from_namespace`, and it only
      // draws a text box at all when its derivation came back empty —
      // so this is exactly the path where the placeholder is read.
      visit('?guide=wall&method=separate-wall');
      mockFetch((url) =>
        url.includes('/resolve')
          ? {
              ...RESOLVED_WITH_PARTS,
              refinements: [
                {
                  key: 'side-clips',
                  role: 'wall',
                  prompt: 'Side clips',
                  from_combination: 'connection',
                  unavailable: [],
                  because: {},
                  recommended: null,
                  selected: null,
                },
              ],
            }
          : GUIDE_DOCUMENT
      );

      render(<GuidePage />);

      expect(
        await screen.findByPlaceholderText('connection|...')
      ).toBeInTheDocument();
      expect(
        screen.queryByPlaceholderText('undefined|...')
      ).not.toBeInTheDocument();
    });

    it('explains the options in the other column while the question stands', async () => {
      // The first screen has no parts to show, and the difference
      // between three ways of building a wall is the whole decision.
      visit('?guide=wall');
      mockFetch((url) => (url.includes('/resolve') ? RESOLVED : GUIDE_DOCUMENT));

      render(<GuidePage />);

      expect(
        await screen.findByRole('heading', { name: 'What these mean' })
      ).toBeInTheDocument();
      expect(
        screen.getByText(/Floor and wall are independent\./)
      ).toBeInTheDocument();
      expect(
        screen.getByText('Everything prints separately and stacks.')
      ).toBeInTheDocument();
    });

    it('brings the explanation back when a settled question is reopened', async () => {
      // Going back to a choice is exactly when its explanation is
      // wanted again — that is what reopening it is for — and it must
      // not be the outstanding question's explanation that shows.
      visit('?guide=wall&method=separate-wall');
      const withSize = {
        ...RESOLVED_WITH_PARTS,
        steps: [
          ...RESOLVED_WITH_PARTS.steps,
          {
            key: 'size',
            prompt: 'What size tiles?',
            selected: null,
            options: [
              { key: '1x1', title: '1×1', blurb: 'One tile.', roles: {} },
            ],
          },
        ],
      };
      mockFetch((url) => (url.includes('/resolve') ? withSize : GUIDE_DOCUMENT));

      render(<GuidePage />);
      // The outstanding question is explained to begin with.
      expect(await screen.findByText('One tile.')).toBeInTheDocument();

      fireEvent.click(screen.getByRole('button', { name: /Separate wall/ }));

      // Now the reopened one is, including the answers not taken.
      expect(
        screen.getByText(/Floor and wall are independent\./)
      ).toBeInTheDocument();
      expect(
        screen.getByText('Everything prints separately and stacks.')
      ).toBeInTheDocument();
      expect(screen.queryByText('One tile.')).not.toBeInTheDocument();
    });

    it('never answers a reopening with the other questions', async () => {
      // A question with nothing written about it used to fall through
      // to "what you chose", so clicking one settled question printed
      // a summary of all of them — which reads as though the click did
      // something else entirely. Nothing to say means say nothing.
      visit('?guide=wall&method=separate-wall');
      const withPlainSize = {
        ...RESOLVED_WITH_PARTS,
        steps: [
          ...RESOLVED_WITH_PARTS.steps,
          {
            key: 'size',
            prompt: 'What size tiles?',
            selected: '1x1',
            options: [{ key: '1x1', title: '1×1', roles: {} }],
          },
        ],
      };
      mockFetch((url) =>
        url.includes('/resolve') ? withPlainSize : GUIDE_DOCUMENT
      );

      render(<GuidePage />);
      await screen.findByRole('heading', { name: 'What you chose' });

      fireEvent.click(screen.getByRole('button', { name: /What size tiles/ }));

      expect(
        screen.queryByRole('heading', { name: 'What you chose' })
      ).not.toBeInTheDocument();
      expect(
        screen.queryByText(/Floor and wall are independent\./)
      ).not.toBeInTheDocument();
    });

    it('does not confuse two questions that share an option key', async () => {
      // Option keys are only unique within their own question, and the
      // wall guide really does have two that share one: wall-print and
      // floor-print both offer `with-base`. Keyed on the option alone,
      // React matches the old card to the new one across a change of
      // question and keeps drawing a card whose question is gone.
      //
      // It takes a transition to show: on a first paint a duplicate
      // key still renders both.
      const printStep = (key: string, title: string, blurb: string) => ({
        key,
        prompt: `How should the ${key} print?`,
        selected: 'with-base',
        options: [{ key: 'with-base', title, blurb, roles: {} }],
      });
      const bothPrints = {
        ...RESOLVED_WITH_PARTS,
        steps: [
          ...RESOLVED_WITH_PARTS.steps,
          printStep('wall-print', 'Wall plus a base', 'The wall drops into a base.'),
          printStep('floor-print', 'Floor plus a base', 'The tile sits in a base.'),
        ],
      };
      // Choosing wall-on-tile gates both print questions away.
      const noPrints = {
        ...RESOLVED_WITH_PARTS,
        steps: [
          {
            ...RESOLVED_WITH_PARTS.steps[0],
            selected: 's2w',
          },
        ],
      };
      visit('?guide=wall&method=separate-wall');
      let resolved: unknown = bothPrints;
      mockFetch((url) => (url.includes('/resolve') ? resolved : GUIDE_DOCUMENT));

      render(<GuidePage />);
      expect(
        await screen.findByText('The wall drops into a base.')
      ).toBeInTheDocument();

      resolved = noPrints;
      fireEvent.click(screen.getByRole('button', { name: /Separate wall/ }));
      fireEvent.click(screen.getByRole('button', { name: /Modular \(s2w\)/ }));

      // Both print questions are gone, so neither card may survive.
      await screen.findByText('Everything prints separately and stacks.');
      expect(
        screen.queryByText('The wall drops into a base.')
      ).not.toBeInTheDocument();
      expect(
        screen.queryByText('The tile sits in a base.')
      ).not.toBeInTheDocument();
    });

    it('links the makers a description names', async () => {
      // The names live in the prose and the URLs beside it, so an
      // author writes a sentence rather than markup — and a name that
      // appears twice links twice without them thinking about it.
      visit('?guide=wall');
      mockFetch((url) => (url.includes('/resolve') ? RESOLVED : GUIDE_DOCUMENT));

      render(<GuidePage />);

      const links = await screen.findAllByRole('link', {
        name: 'Printable Scenery',
      });
      expect(links).toHaveLength(2);
      expect(links[0]).toHaveAttribute('href', 'https://www.printablescenery.com');
      // Opening someone else's site should not navigate away from a
      // build in progress, and an untrusted target needs the opener
      // severed.
      expect(links[0]).toHaveAttribute('target', '_blank');
      expect(links[0]).toHaveAttribute('rel', expect.stringContaining('noopener'));
    });

    it('explains a question that carries prose of its own', async () => {
      // Not every question is explained by its answers. What is true
      // of the size question — that sizes are in inches, that a 1 inch
      // hallway does not fit a mini — belongs to the question, and
      // repeating it on eight buttons would be absurd.
      visit('?guide=wall&method=separate-wall');
      const withPreamble = {
        ...RESOLVED_WITH_PARTS,
        steps: [
          ...RESOLVED_WITH_PARTS.steps,
          {
            key: 'size',
            prompt: 'What size tiles?',
            blurb: 'All tile sizes are in inches.\n\nOne inch is tight.',
            selected: null,
            options: [{ key: '2x2', title: '2×2', roles: {} }],
          },
        ],
      };
      mockFetch((url) =>
        url.includes('/resolve') ? withPreamble : GUIDE_DOCUMENT
      );

      render(<GuidePage />);

      expect(
        await screen.findByRole('heading', { name: 'What these mean' })
      ).toBeInTheDocument();
      // Both paragraphs, and not the previous question's explanation.
      expect(
        screen.getByText('All tile sizes are in inches.')
      ).toBeInTheDocument();
      expect(screen.getByText('One inch is tight.')).toBeInTheDocument();
      expect(
        screen.queryByText(/Floor and wall are independent\./)
      ).not.toBeInTheDocument();
    });

    it('explains what was chosen when the open question has nothing to say', async () => {
      // "What size tiles?" is eight numbers; explaining them would be
      // padding. Rather than leave a third of the page blank for it,
      // the column keeps explaining the choices already made.
      visit('?guide=wall&method=separate-wall');
      const withSize = {
        ...RESOLVED_WITH_PARTS,
        steps: [
          ...RESOLVED_WITH_PARTS.steps,
          {
            key: 'size',
            prompt: 'What size tiles?',
            selected: null,
            options: [
              { key: '1x1', title: '1×1', roles: {} },
              { key: '2x2', title: '2×2', roles: {} },
            ],
          },
        ],
      };
      mockFetch((url) => (url.includes('/resolve') ? withSize : GUIDE_DOCUMENT));

      render(<GuidePage />);

      expect(
        await screen.findByRole('heading', { name: 'What you chose' })
      ).toBeInTheDocument();
      expect(
        screen.getByText(/Floor and wall are independent\./)
      ).toBeInTheDocument();
    });

    it('explains what was chosen once there is nothing left to ask', async () => {
      // The column does not go blank when the questions run out: the
      // same words are still the reason this build is this build. What
      // changes is that only the chosen answer is described — the ones
      // not taken are no longer a choice to explain.
      visit('?guide=wall&method=separate-wall');
      mockFetch((url) =>
        url.includes('/resolve') ? RESOLVED_WITH_PARTS : GUIDE_DOCUMENT
      );

      render(<GuidePage />);
      await screen.findByText('a dungeon stone wall');

      expect(
        screen.getByRole('heading', { name: 'What you chose' })
      ).toBeInTheDocument();
      expect(
        screen.queryByRole('heading', { name: 'What these mean' })
      ).not.toBeInTheDocument();
      expect(
        screen.getByText(/Floor and wall are independent\./)
      ).toBeInTheDocument();
      expect(
        screen.queryByText('Everything prints separately and stacks.')
      ).not.toBeInTheDocument();
    });

    it('draws a closed refinement as buttons, and answers with one', async () => {
      visit('?guide=wall&method=separate-wall');
      mockFetch((url) =>
        url.includes('/resolve') ? RESOLVED_WITH_PARTS : GUIDE_DOCUMENT
      );

      render(<GuidePage />);
      // No text box for this one, and a label made from the tag when
      // the choice carries no title.
      const cave = await screen.findByRole('button', { name: 'Cave' });
      expect(
        screen.getByRole('button', { name: 'Dungeon stone' })
      ).toBeInTheDocument();
      expect(
        screen.queryByPlaceholderText('texture|...')
      ).toBeInTheDocument(); // the open one is still a box

      fireEvent.click(cave);

      await waitFor(() =>
        expect(window.location.search).toContain(
          'floor-texture=texture%7Ccave'
        )
      );
    });

    it('clears a closed refinement by picking its answer again', async () => {
      visit('?guide=wall&method=separate-wall&floor-texture=texture|cave');
      mockFetch((url) =>
        url.includes('/resolve')
          ? {
              ...RESOLVED_WITH_PARTS,
              refinements: RESOLVED_WITH_PARTS.refinements.map((r) =>
                r.key === 'floor-texture'
                  ? { ...r, selected: 'texture|cave' }
                  : r
              ),
            }
          : GUIDE_DOCUMENT
      );

      render(<GuidePage />);
      // Folded to its answer; open it to change your mind.
      fireEvent.click(await screen.findByRole('button', { name: /Cave/ }));
      const cave = screen.getByRole('button', { name: 'Cave' });
      expect(cave).toHaveAttribute('aria-pressed', 'true');

      fireEvent.click(cave);

      await waitFor(() =>
        expect(window.location.search).not.toContain('floor-texture')
      );
    });

    it('turns every part together when the list is dragged', async () => {
      // The pieces are different sheets, so they are kept in step by
      // angle *name*. A list where one piece faced another way would
      // be answering a different question.
      visit('?guide=wall&method=separate-wall');
      mockFetch((url) =>
        url.includes('/resolve') ? RESOLVED_WITH_PARTS : GUIDE_DOCUMENT
      );

      render(<GuidePage />);
      const sprite = await screen.findByLabelText(
        /a dungeon stone wall, seen from the front/
      );
      const surface = sprite.closest('.guide-parts')!.querySelector('.select-none')!;

      // Two thresholds to the right is two steps round the ring.
      fireEvent.mouseDown(surface, { button: 0, clientX: 100, clientY: 100 });
      fireEvent.mouseMove(window, { clientX: 162, clientY: 100 });
      fireEvent.mouseUp(window);

      // The base has a `right` frame and turns to it.
      expect(
        screen.getByLabelText(/a dungeon stone base, seen from the right/)
      ).toBeInTheDocument();
      // The wall's sheet declares only `back` and `front`, so it falls
      // back to its default frame — and says which side that is. It
      // used to claim "seen from the right" while drawing the back,
      // which is the one thing a label must not do.
      expect(
        screen.getByLabelText(/a dungeon stone wall, seen from the back/)
      ).toBeInTheDocument();
      expect(
        screen.queryByLabelText(/a dungeon stone wall, seen from the right/)
      ).toBeNull();
      // And it is not only the label that says so: a sheet missing a
      // side is a generation gap, so it reaches the console too.
      expect(console.warn).toHaveBeenCalledWith(
        'sprite for %s has no %s angle',
        'a dungeon stone wall',
        'right'
      );
    });

    it('takes every piece to a pole on a decisive vertical drag', async () => {
      // The parts list wires `onVertical` at all, which nothing here
      // covered — the shared hook's vertical arm was held only by the
      // older sprite-viewer tests, on the other consumer.
      visit('?guide=wall&method=separate-wall');
      mockFetch((url) =>
        url.includes('/resolve') ? RESOLVED_WITH_PARTS : GUIDE_DOCUMENT
      );

      render(<GuidePage />);
      const sprite = await screen.findByLabelText(
        /a dungeon stone base, seen from the front/
      );
      const surface = sprite
        .closest('.guide-parts')!
        .querySelector('.select-none')!;

      // Mostly upward and past the threshold: straight to the top,
      // rather than a step round the ring.
      fireEvent.mouseDown(surface, { button: 0, clientX: 100, clientY: 200 });
      fireEvent.mouseMove(window, { clientX: 110, clientY: 100 });
      fireEvent.mouseUp(window);

      expect(
        screen.getByLabelText(/a dungeon stone base, seen from the top/)
      ).toBeInTheDocument();
    });

    it('turns the same distance whichever way the drag goes', async () => {
      // 45px is one and a half thresholds. `Math.floor` gave 1 step
      // right and -2 left, so the same gesture turned further one way
      // than the other; `Math.trunc` gives 1 either way. Both the
      // existing page drags are rightward and whole multiples, where
      // the two agree — which is why the fix was unpinned.
      visit('?guide=wall&method=separate-wall');
      mockFetch((url) =>
        url.includes('/resolve') ? RESOLVED_WITH_PARTS : GUIDE_DOCUMENT
      );

      render(<GuidePage />);
      const sprite = await screen.findByLabelText(
        /a dungeon stone base, seen from the front/
      );
      const surface = sprite.closest('.guide-parts')!.querySelector('.select-none')!;

      // On the side widget rather than a picture: it is keyed by
      // angle name, so it reports the view the drag reached whether
      // or not a given sheet has a frame for it.
      expect(screen.getByRole('button', { name: 'front' })).toHaveAttribute(
        'aria-pressed',
        'true'
      );

      // One and a half thresholds to the LEFT: one step back, the
      // same distance the identical rightward drag would travel.
      fireEvent.mouseDown(surface, { button: 0, clientX: 100, clientY: 100 });
      fireEvent.mouseMove(window, { clientX: 55, clientY: 100 });
      fireEvent.mouseUp(window);

      expect(
        screen.getByRole('button', { name: 'front-left' })
      ).toHaveAttribute('aria-pressed', 'true');
    });

    it('does not open the tag search at the end of a drag', async () => {
      // The picture is also the button that opens the search, so
      // letting go after turning it must not count as a click.
      visit('?guide=wall&method=separate-wall');
      mockFetch((url) =>
        url.includes('/resolve') ? RESOLVED_WITH_PARTS : GUIDE_DOCUMENT
      );

      render(<GuidePage />);
      const sprite = await screen.findByLabelText(/a dungeon stone wall, seen/);
      const surface = sprite.closest('.guide-parts')!.querySelector('.select-none')!;

      fireEvent.mouseDown(surface, { button: 0, clientX: 100, clientY: 100 });
      fireEvent.mouseMove(window, { clientX: 200, clientY: 100 });
      fireEvent.mouseUp(window);
      fireEvent.click(sprite.closest('button')!);

      expect(screen.queryByTestId('part-modal')).not.toBeInTheDocument();
    });

    it('does not open the tag search at the end of a vertical drag either', async () => {
      // Only the horizontal handler was covered, so the `turned` flag
      // could be dropped from the vertical one and a drag to a pole
      // would open the dialog on release.
      visit('?guide=wall&method=separate-wall');
      mockFetch((url) =>
        url.includes('/resolve') ? RESOLVED_WITH_PARTS : GUIDE_DOCUMENT
      );

      render(<GuidePage />);
      const sprite = await screen.findByLabelText(/a dungeon stone wall, seen/);
      const surface = sprite
        .closest('.guide-parts')!
        .querySelector('.select-none')!;

      fireEvent.mouseDown(surface, { button: 0, clientX: 100, clientY: 200 });
      fireEvent.mouseMove(window, { clientX: 105, clientY: 100 });
      fireEvent.mouseUp(window);
      fireEvent.click(sprite.closest('button')!);

      expect(screen.queryByTestId('part-modal')).not.toBeInTheDocument();
    });

    it('drops an answer the catalog cannot supply, and says why', async () => {
      // Availability is its own request and arrives after the parts.
      // `texture` answered, so floor-texture is the question the third
      // column is explaining and its dropped answer has somewhere to
      // visibly not be.
      visit('?guide=wall&method=separate-wall&texture=texture|dungeon_stone');
      global.fetch = jest.fn((url: string) => {
        const body = url.includes('/availability')
          ? {
              unavailable: { 'floor-texture': ['texture|cave'] },
              because: {
                'floor-texture': {
                  'texture|cave': { part: 'Floor', question: 'size', prompt: 'What size?' },
                },
              },
            }
          : url.includes('/resolve')
            ? {
                ...RESOLVED_WITH_PARTS,
                refinements: RESOLVED_WITH_PARTS.refinements.map((r) =>
                  r.key === 'texture'
                    ? { ...r, selected: 'texture|dungeon_stone' }
                    : r
                ),
              }
            : GUIDE_DOCUMENT;
        return Promise.resolve({
          ok: true,
          status: 200,
          json: () => Promise.resolve(body),
        });
      }) as unknown as typeof fetch;

      render(<GuidePage />);

      await screen.findByRole('button', { name: 'Dungeon stone' });
      // Gone entirely once availability lands, and accounted for —
      // naming the part it would empty and the answer at fault, so
      // its absence is not a mystery.
      expect(
        screen.getByText(/Cave — no Floor for your "What size\?" answer/)
      ).toBeInTheDocument();
      expect(screen.queryByRole('button', { name: 'Cave' })).toBeNull();
      // And not described in the column beside it either, which would
      // read as though the choice is there and cannot be found.
      expect(screen.queryByText('Lumpy and irregular.')).not.toBeInTheDocument();
      // The answers that do work are still on offer.
      expect(
        screen.getByRole('button', { name: 'Dungeon stone' })
      ).toBeInTheDocument();
    });

    it('drops a step answer too, not only a refinement', async () => {
      // Steps and refinements are the same question to the person
      // answering, and a dead answer is as useless in either.
      visit('?guide=wall');
      global.fetch = jest.fn((url: string) => {
        const body = url.includes('/availability')
          ? {
              unavailable: { method: ['s2w'] },
              because: { method: { s2w: { part: 'Wall' } } },
            }
          : url.includes('/resolve')
            ? RESOLVED
            : GUIDE_DOCUMENT;
        return Promise.resolve({
          ok: true,
          status: 200,
          json: () => Promise.resolve(body),
        });
      }) as unknown as typeof fetch;

      render(<GuidePage />);

      await screen.findByRole('button', { name: /Separate wall/ });
      await waitFor(() =>
        expect(screen.queryByRole('button', { name: /Modular/ })).toBeNull()
      );
      // No single answer is to blame, so it says the honest half.
      expect(screen.getByText(/Modular \(s2w\) — no Wall$/)).toBeInTheDocument();
    });

    it('drops a yes/no the catalog cannot answer', async () => {
      // Pegs in a texture that has none is not a decision, and a
      // checkbox you cannot tick is worse than no checkbox.
      visit('?guide=wall&method=separate-wall');
      global.fetch = jest.fn((url: string) => {
        const body = url.includes('/availability')
          ? { unavailable: { 'side-locks': ['on'] }, because: {} }
          : url.includes('/resolve')
            ? RESOLVED_WITH_PARTS
            : GUIDE_DOCUMENT;
        return Promise.resolve({
          ok: true,
          status: 200,
          json: () => Promise.resolve(body),
        });
      }) as unknown as typeof fetch;

      render(<GuidePage />);

      await screen.findByRole('button', { name: 'Dungeon stone' });
      expect(screen.queryByRole('checkbox', { name: 'Side locks' })).toBeNull();
      // And the heading over it goes with it, rather than standing
      // over an empty section.
      expect(screen.queryByText('Side locks')).toBeNull();
    });

    it('stays usable when availability never arrives', async () => {
      // Greying is an improvement on a working page, not part of it.
      visit('?guide=wall&method=separate-wall');
      global.fetch = jest.fn((url: string) => {
        if (url.includes('/availability')) {
          return Promise.resolve({ ok: false, status: 500, json: () => Promise.resolve({}) });
        }
        return Promise.resolve({
          ok: true,
          status: 200,
          json: () =>
            Promise.resolve(
              url.includes('/resolve') ? RESOLVED_WITH_PARTS : GUIDE_DOCUMENT
            ),
        });
      }) as unknown as typeof fetch;

      render(<GuidePage />);

      expect(await screen.findByRole('button', { name: 'Cave' })).not.toBeDisabled();
      expect(await screen.findByText('a dungeon stone wall')).toBeInTheDocument();
    });

    it('does not apply one answer\'s dead-set to another answer\'s parts', async () => {
      // Availability and resolve are separate round trips, so they can
      // land out of order. The dead-set hides answers and drives the
      // "N options" bar, so pairing it with the wrong resolution
      // removes options that really are there. The pairing is by the
      // selections each one answers, not by the URL — the resolution
      // is deliberately allowed to lag.
      visit('?guide=wall&method=separate-wall');
      const seen: string[] = [];
      global.fetch = jest.fn((url: string) => {
        seen.push(url);
        // Availability answers for the *new* selections; resolve
        // fails, so the page keeps the parts for the old ones.
        // Only the *second* availability — the one for the answered
        // texture — carries a dead-set. The first must stay empty, or
        // the assertion cannot tell a correctly paired bar from a
        // mismatched one.
        const answered = url.includes('texture=');
        const body = url.includes('/availability')
          ? answered
            ? {
                unavailable: { texture: ['texture|cave'] },
                because: {},
                options: { wall: 4 },
              }
            : { unavailable: {}, because: {}, options: {} }
          : url.includes('/resolve')
            ? RESOLVED_WITH_PARTS
            : GUIDE_DOCUMENT;
        const failing = url.includes('/resolve') && answered;
        return Promise.resolve({
          ok: !failing,
          status: failing ? 500 : 200,
          statusText: failing ? 'Server Error' : 'OK',
          json: () => Promise.resolve(body),
        });
      }) as unknown as typeof fetch;

      render(<GuidePage />);
      await screen.findByRole('button', { name: 'Cave' });

      // Answer the texture. Resolve 500s and the old parts are kept;
      // availability succeeds for the new selections.
      fireEvent.click(screen.getByRole('button', { name: 'Cave' }));

      // Wait for the *error* rather than for the request to be sent:
      // it proves the failed resolve was processed and the old parts
      // kept, and the availability effect runs after it in the same
      // tick, so its response has landed too. Asserting on the
      // request alone let both arms of the mutation look identical.
      await screen.findByText(/Server Error/);
      await waitFor(() =>
        expect(
          seen.filter((u) => u.includes('/availability')).length
        ).toBeGreaterThan(1)
      );

      // The new dead-set must not reach the old parts: Cave is still
      // offered, and no options bar from the mismatched payload.
      expect(screen.getByRole('button', { name: 'Cave' })).toBeInTheDocument();
      expect(screen.queryByRole('button', { name: '4 options' })).toBeNull();
    });

    it('keeps the questions on screen when a later resolve fails', async () => {
      // The selections live only in the URL, so dropping the last good
      // resolution leaves a heading, a red line, and no control that
      // can change the state that caused the failure.
      visit('?guide=wall&method=separate-wall');
      let calls = 0;
      global.fetch = jest.fn((url: string) => {
        if (!url.includes('/resolve')) {
          return Promise.resolve({
            ok: true,
            status: 200,
            json: () =>
              Promise.resolve(
                url.includes('/availability')
                  ? { unavailable: {}, because: {}, options: {} }
                  : GUIDE_DOCUMENT
              ),
          });
        }
        calls += 1;
        // The first resolve succeeds; the second fails.
        const failing = calls > 1;
        return Promise.resolve({
          ok: !failing,
          status: failing ? 500 : 200,
          statusText: failing ? 'Server Error' : 'OK',
          json: () => Promise.resolve(failing ? {} : RESOLVED_WITH_PARTS),
        });
      }) as unknown as typeof fetch;

      render(<GuidePage />);
      await screen.findByRole('button', { name: 'Cave' });

      fireEvent.click(screen.getByRole('button', { name: 'Cave' }));

      // The error is shown, and the questions survive it, so the
      // person can answer their way back out.
      await screen.findByText(/500/);
      expect(screen.getByRole('button', { name: 'Dungeon stone' })).toBeInTheDocument();
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

      // An answered question collapses to its answer, so that is where
      // "which one did I pick" is shown. The other options are not on
      // screen at all until it is reopened.
      const summary = await screen.findByRole('button', {
        name: /Separate wall/,
      });
      expect(summary).toHaveAttribute('aria-expanded', 'false');
      expect(
        screen.queryByRole('button', { name: /Modular \(s2w\)/ })
      ).not.toBeInTheDocument();

      // Reopening shows every option, with the chosen one pressed.
      fireEvent.click(summary);

      expect(
        screen.getByRole('button', { name: /Separate wall/ })
      ).toHaveAttribute('aria-pressed', 'true');
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

      // Answered, so it is folded to its answer — and that is where
      // the answer is shown now.
      const summary = await screen.findByRole('button', {
        name: /texture\|dungeon_stone/,
      });
      expect(summary).toHaveAttribute('aria-expanded', 'false');

      // Reopened, the box still arrives filled in: `defaultValue` is
      // what does that, and an uncontrolled input reads empty without
      // it whatever the refinement says.
      fireEvent.click(summary);
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
      fireEvent.click(
        await screen.findByRole('button', { name: /Separate wall/ })
      );
      await waitFor(() => expect(pending).toHaveLength(1));
      fireEvent.click(screen.getByRole('button', { name: /Modular \(s2w\)/ }));
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
      // than on the guard. A macrotask boundary rather than a count
      // of microtask flushes: a setTimeout callback runs only once
      // the queue is drained, whatever the promise chain's depth, so
      // there is no tick count here to be coupled to the
      // implementation. The two flushes this replaced did in fact
      // still catch the regression with three extra hops added to
      // that chain — `act` drains microtasks itself — so this is
      // removing a dependency, not fixing a demonstrated break.
      await act(async () => {
        await new Promise((resolve) => setTimeout(resolve, 0));
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

      // One: the floor base resolved to no blueprint at all. The two
      // parts that did resolve both carry a sheet.
      expect(screen.getAllByText('no picture')).toHaveLength(1);
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

    it('does not claim a guide is missing when the server merely failed', async () => {
      // The side the distinction was added for, and the side that had
      // no test: a 500 or a dropped connection told the person their
      // guide did not exist and sent them off to check a URL that was
      // fine.
      visit('?guide=wall');
      global.fetch = jest.fn(() =>
        Promise.resolve({
          ok: false,
          status: 500,
          statusText: 'Server Error',
          json: () => Promise.resolve({}),
        })
      ) as unknown as typeof fetch;

      render(<GuidePage />);

      expect(await screen.findByText(/Could not load 'wall'/)).toBeInTheDocument();
      expect(screen.queryByText("No guide called 'wall'.")).toBeNull();
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

    render(<GuidePage />);
    await screen.findByText('a dungeon stone wall');

    // The back/forward case: the component stays mounted and the URL
    // changes underneath it. No `rerender` here on purpose — the
    // popstate subscription is the thing under test, and re-rendering
    // by hand would drive the update whether or not it is wired.
    await act(async () => {
      window.history.replaceState({}, '', '/guides/?guide=floor&style=flagstone');
      window.dispatchEvent(new PopStateEvent('popstate'));
    });

    await waitFor(() =>
      expect(urls).toContain('/api/guides/floor/resolve?style=flagstone')
    );
    expect(
      urls.filter((url) => url.includes('/floor/resolve') && url.includes('method='))
    ).toEqual([]);
  });

  /**
   * Both halves of the same hazard, and both need the second guide's
   * fetch held open: the bad state is the tick between the key
   * changing and the answer arriving, and in jsdom an unheld fetch
   * closes that window before anything can be asserted in it.
   */
  function movingToFloor() {
    const pending: ((value: unknown) => void)[] = [];
    let holdDocument = false;
    let holdResolve = false;
    const floorDocument = {
      guide_key: 'floor',
      document: {
        key: 'floor',
        title: 'How do I make a floor?',
        steps: [{ key: 'style', prompt: 'Which style?', options: [] }],
        refinements: [],
        roles: {},
      },
    };
    global.fetch = jest.fn((url: string) => {
      const held = () => new Promise((resolve) => pending.push(resolve));
      let body: unknown;
      if (url.includes('/floor/resolve')) {
        body = holdResolve ? held() : Promise.resolve(EMPTY_RESOLVED);
      } else if (url.includes('/api/guides/floor')) {
        body = holdDocument ? held() : Promise.resolve(floorDocument);
      } else if (url.includes('/resolve')) {
        body = Promise.resolve(RESOLVED_WITH_PARTS);
      } else {
        body = Promise.resolve(GUIDE_DOCUMENT);
      }
      return Promise.resolve({ ok: true, status: 200, json: () => body });
    }) as unknown as typeof fetch;
    return {
      pending,
      floorDocument,
      hold: (what: 'document' | 'resolve') => {
        holdDocument = what === 'document';
        holdResolve = what === 'resolve';
      },
      go: async () => {
        await act(async () => {
          window.history.replaceState({}, '', '/guides/?guide=floor');
          window.dispatchEvent(new PopStateEvent('popstate'));
        });
      },
    };
  }

  it("does not show one guide's parts under the next guide's title", async () => {
    // The resolution arrives a tick after the document. Held unkeyed,
    // that tick renders the new guide's heading over the old guide's
    // parts, with a Download button that works and fetches the wrong
    // pieces.
    visit('?guide=wall&method=separate-wall');
    const floor = movingToFloor();

    render(<GuidePage />);
    await screen.findByText('a dungeon stone wall');

    floor.hold('resolve');
    await floor.go();

    // The floor document has landed; its answer has not.
    await screen.findByRole('heading', { name: 'How do I make a floor?' });
    expect(screen.queryByText('a dungeon stone wall')).not.toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: /^Download/ })
    ).not.toBeInTheDocument();
  });

  it("does not ask the next guide with the last guide's document", async () => {
    // The document lags the key by a fetch, and the document is what
    // decides which query parameters belong to this guide. Held
    // unkeyed, the floor guide is asked using the wall's vocabulary.
    visit('?guide=wall&method=separate-wall');
    const floor = movingToFloor();

    render(<GuidePage />);
    await screen.findByText('a dungeon stone wall');

    floor.hold('document');
    await floor.go();

    // The key is floor and no floor document has arrived, so there is
    // nothing this page can honestly show yet — and above all not the
    // wall's question still sitting there answered.
    expect(
      screen.queryByRole('heading', { name: 'How do I make a wall?' })
    ).not.toBeInTheDocument();
    expect(screen.queryByText('a dungeon stone wall')).not.toBeInTheDocument();
  });
});

describe('inspecting a part', () => {
  it('opens the tag search on this part, with its preferences droppable', async () => {
    visit('?guide=wall&method=separate-wall');
    mockFetch((url) =>
      url.includes('/resolve') ? RESOLVED_WITH_PARTS : GUIDE_DOCUMENT
    );

    render(<GuidePage />);
    fireEvent.click(await screen.findByLabelText(/a dungeon stone wall, seen/));

    expect(await screen.findByTestId('part-modal')).toBeInTheDocument();
    const opened = modalProps[modalProps.length - 1];
    expect(opened.partName).toBe('Wall (wall)');
    // What the guide resolved, texture and all: opening on your own
    // wall is the useful place to start looking for another one.
    //
    // `accept` is absent on purpose. The search has no subtree
    // predicate, so passing one would be seeding the modal with a
    // term that is silently discarded — and a discarded restriction
    // is a wider set, which is the failure this assertion exists to
    // catch.
    expect(opened.configValues).toEqual({
      require: [{ tag: 'shape|wall' }, { tag: 'texture|dungeon_stone' }],
      deny: [],
      deny_children: [{ tag: 'component|wall' }],
      allow: [{ tag: 'shape|square' }],
    });
    expect(opened.configValues).not.toHaveProperty('accept');
    // And the texture comes off from inside, so leaving the family is
    // a deliberate click rather than the default.
    expect(opened.removable).toEqual(['texture|dungeon_stone']);
  });

  it('offers the other pieces when the answer left more than one', async () => {
    // "Towne" is six walls and "dungeon stone" is one, and nothing on
    // the page said so. The count is how many pieces the part's own
    // predicate matches, so it is also what the dialog will show.
    visit('?guide=wall&method=separate-wall');
    mockFetch((url) =>
      url.includes('/availability')
        ? { unavailable: {}, because: {}, options: { wall: 6, 'wall-base': 1 } }
        : url.includes('/resolve')
          ? RESOLVED_WITH_PARTS
          : GUIDE_DOCUMENT
    );

    render(<GuidePage />);
    const more = await screen.findByRole('button', { name: '6 options' });

    // One piece behind an answer is the guide having decided, and not
    // worth a control.
    expect(screen.queryByRole('button', { name: '1 options' })).toBeNull();
    // It opens the same dialog the picture does.
    fireEvent.click(more);
    expect(await screen.findByTestId('part-modal')).toBeInTheDocument();
    expect(modalProps[modalProps.length - 1].partName).toBe('Wall (wall)');
  });

  it('offers the other pieces on the answer that left them, too', async () => {
    // Answering "towne" is where you find out there are six of them,
    // so the count belongs beside the answer as well as on the part —
    // and it opens the same dialog, on the part that question
    // narrows rather than on whichever was clicked last.
    visit('?guide=wall&method=separate-wall&texture=texture|cave');
    mockFetch((url) =>
      url.includes('/availability')
        ? // Both the wall and the base under it still have a choice
          // in them, and the texture question narrows both. The one
          // worth offering is the one with the most left.
          { unavailable: {}, because: {}, options: { wall: 6, 'wall-base': 3 } }
        : url.includes('/resolve')
          ? {
              ...RESOLVED_WITH_PARTS,
              refinements: RESOLVED_WITH_PARTS.refinements.map((r) =>
                r.key === 'texture' ? { ...r, selected: 'texture|cave' } : r
              ),
            }
          : GUIDE_DOCUMENT
    );

    render(<GuidePage />);
    // Two of them: one on the part, one on the settled question.
    const bars = await screen.findAllByRole('button', { name: '6 options' });
    expect(bars).toHaveLength(2);

    // The one in the question column opens the wall, which is the
    // part that question narrows — not whichever part was clicked
    // last, because nothing was.
    const asked = bars.find((bar) => !bar.closest('.guide-parts'))!;
    expect(asked).toBeDefined();
    fireEvent.click(asked);
    expect(await screen.findByTestId('part-modal')).toBeInTheDocument();
    expect(modalProps[modalProps.length - 1].partName).toBe('Wall (wall)');
  });

  it('opens showing the part that was clicked', async () => {
    // You were looking at it when you clicked it. Opening on "No
    // Blueprint Selected" and a list would make you go and find the
    // thing you already had.
    visit('?guide=wall&method=separate-wall');
    mockFetch((url) =>
      url.includes('/resolve') ? RESOLVED_WITH_PARTS : GUIDE_DOCUMENT
    );

    render(<GuidePage />);
    fireEvent.click(await screen.findByLabelText(/a dungeon stone wall, seen/));

    await screen.findByTestId('part-modal');
    expect(modalProps[modalProps.length - 1].initialMd5).toBe('abc');
  });

  it('pins the part the person chose, and says whose choice it is', async () => {
    visit('?guide=wall&method=separate-wall');
    mockFetch((url) =>
      url.includes('/resolve') ? RESOLVED_WITH_PARTS : GUIDE_DOCUMENT
    );

    render(<GuidePage />);
    fireEvent.click(await screen.findByLabelText(/a dungeon stone wall, seen/));
    await screen.findByTestId('part-modal');

    const onPartSelected = modalProps[modalProps.length - 1]
      .onPartSelected as (name: string, blueprint: { file_md5: string }) => void;
    act(() => onPartSelected('Wall (wall)', { file_md5: 'chosen-md5' }));

    // The pin is a selection like any other, so it lands in the URL
    // and the link still describes the whole build.
    expect(window.location.search).toContain('part.wall=chosen-md5');
    // And the dialog closes: the question it was open to answer has
    // been answered.
    expect(screen.queryByTestId('part-modal')).not.toBeInTheDocument();
  });

  it('brings the questions that part answers into line with it', async () => {
    // Picking a cave wall out of the catalog while the texture
    // question says dungeon stone leaves the page contradicting
    // itself. The questions the piece answers are reset to what it is
    // — and in one write, because the URL is the state and two writes
    // would lose the first.
    visit('?guide=wall&method=separate-wall&texture=texture|dungeon_stone');
    mockFetch((url) =>
      url.includes('/resolve')
        ? {
            ...RESOLVED_WITH_PARTS,
            refinements: RESOLVED_WITH_PARTS.refinements.map((r) =>
              r.key === 'texture'
                ? {
                    ...r,
                    browsable: true,
                    selected: 'texture|dungeon_stone',
                    choices: [
                      { tag: 'texture|dungeon_stone' },
                      { tag: 'texture|cave' },
                    ],
                  }
                : r
            ),
          }
        : GUIDE_DOCUMENT
    );

    render(<GuidePage />);
    fireEvent.click(await screen.findByLabelText(/a dungeon stone wall, seen/));
    await screen.findByTestId('part-modal');

    const onPartSelected = modalProps[modalProps.length - 1]
      .onPartSelected as (
      name: string,
      blueprint: { file_md5: string; tags: string[] }
    ) => void;
    act(() =>
      onPartSelected('Wall (wall)', {
        file_md5: 'chosen-md5',
        tags: ['shape|wall', 'texture|cave'],
      })
    );

    const search = decodeURIComponent(window.location.search);
    expect(search).toContain('part.wall=chosen-md5');
    expect(search).toContain('texture=texture|cave');
    expect(search).not.toContain('texture=texture|dungeon_stone');
  });

  it('leaves the questions that part does not answer alone', async () => {
    // A question the dialog would not let you cross is not one the
    // dialog may rewrite: whatever was picked already agrees with it.
    visit('?guide=wall&method=separate-wall&texture=texture|dungeon_stone');
    mockFetch((url) =>
      url.includes('/resolve')
        ? {
            ...RESOLVED_WITH_PARTS,
            refinements: RESOLVED_WITH_PARTS.refinements.map((r) =>
              r.key === 'texture'
                ? {
                    ...r,
                    selected: 'texture|dungeon_stone',
                    choices: [
                      { tag: 'texture|dungeon_stone' },
                      { tag: 'texture|cave' },
                    ],
                  }
                : r
            ),
          }
        : GUIDE_DOCUMENT
    );

    render(<GuidePage />);
    fireEvent.click(await screen.findByLabelText(/a dungeon stone wall, seen/));
    await screen.findByTestId('part-modal');

    const onPartSelected = modalProps[modalProps.length - 1]
      .onPartSelected as (
      name: string,
      blueprint: { file_md5: string; tags: string[] }
    ) => void;
    act(() =>
      onPartSelected('Wall (wall)', {
        file_md5: 'chosen-md5',
        tags: ['shape|wall', 'texture|cave'],
      })
    );

    expect(decodeURIComponent(window.location.search)).toContain(
      'texture=texture|dungeon_stone'
    );
  });

  it('marks a pinned part as the person\'s, with a way back', async () => {
    // A pinned part stops answering to the questions on the left, and
    // saying so is the only way the page can explain why changing the
    // texture leaves this one piece alone.
    visit('?guide=wall&method=separate-wall&part.wall=chosen-md5');
    const asked: string[] = [];
    mockFetch((url) => {
      asked.push(url);
      return url.includes('/resolve')
        ? {
            ...RESOLVED_WITH_PARTS,
            parts: RESOLVED_WITH_PARTS.parts.map((p) =>
              p.role === 'wall' ? { ...p, pinned: true } : p
            ),
          }
        : GUIDE_DOCUMENT;
    });

    render(<GuidePage />);
    await screen.findByText('a dungeon stone wall');

    // Forwarded to the backend, or a shared link would resolve
    // without the very part it was shared to show. The page sends
    // only the keys the guide owns, so a pin has to be one of them.
    expect(
      asked.some(
        (url) => url.includes('/resolve') && url.includes('part.wall=chosen-md5')
      )
    ).toBe(true);
    expect(screen.getByText('You picked this part')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'undo' }));
    expect(window.location.search).not.toContain('part.wall');
  });

  it('lets a pinned part go when you answer the question that decides it', async () => {
    // A pinned part outranks the questions, so without this, going
    // back to the texture after hand-picking a wall changes nothing
    // at all and the button looks dead. Answering is the plainest
    // possible way of saying you want the guide to decide it again.
    visit('?guide=wall&method=separate-wall&part.wall=chosen-md5');
    mockFetch((url) =>
      url.includes('/resolve')
        ? {
            ...RESOLVED_WITH_PARTS,
            parts: RESOLVED_WITH_PARTS.parts.map((p) =>
              p.role === 'wall' ? { ...p, pinned: true } : p
            ),
            refinements: RESOLVED_WITH_PARTS.refinements.map((r) =>
              r.key === 'texture'
                ? {
                    ...r,
                    choices: [
                      { tag: 'texture|dungeon_stone', title: 'Dungeon stone' },
                      { tag: 'texture|cave', title: 'Cave' },
                    ],
                  }
                : r
            ),
          }
        : GUIDE_DOCUMENT
    );

    render(<GuidePage />);
    const texture = await screen.findByRole('group', { name: 'Texture' });
    fireEvent.click(within(texture).getByRole('button', { name: 'Dungeon stone' }));

    const search = decodeURIComponent(window.location.search);
    expect(search).toContain('texture=texture|dungeon_stone');
    expect(search).not.toContain('part.wall');
  });

  it('keeps a pinned part when the question does not reach it', async () => {
    // The floor texture has no business dropping a wall somebody
    // chose by hand.
    visit('?guide=wall&method=separate-wall&part.wall=chosen-md5');
    mockFetch((url) =>
      url.includes('/resolve')
        ? {
            ...RESOLVED_WITH_PARTS,
            parts: RESOLVED_WITH_PARTS.parts.map((p) =>
              p.role === 'wall' ? { ...p, pinned: true } : p
            ),
            refinements: RESOLVED_WITH_PARTS.refinements.map((r) =>
              r.key === 'texture' ? { ...r, selected: 'texture|cave' } : r
            ),
          }
        : GUIDE_DOCUMENT
    );

    render(<GuidePage />);
    const floor = await screen.findByRole('group', { name: 'Floor texture' });
    fireEvent.click(within(floor).getByRole('button', { name: 'Dungeon stone' }));

    const search = decodeURIComponent(window.location.search);
    expect(search).toContain('floor-texture=texture|dungeon_stone');
    expect(search).toContain('part.wall=chosen-md5');
  });

  it('reads a toggle answer as words, not as machinery', async () => {
    // A settled toggle folds to "Yes"/"No". Both arms of that were
    // extracted into `answerLabel` and neither was covered before or
    // after — restoring the raw "on"/"off" passed the suite.
    visit('?guide=wall&method=separate-wall&side-locks=on');
    mockFetch((url) =>
      url.includes('/resolve')
        ? {
            ...RESOLVED_WITH_PARTS,
            refinements: RESOLVED_WITH_PARTS.refinements.map((r) =>
              r.key === 'side-locks' ? { ...r, selected: 'on' } : r
            ),
          }
        : GUIDE_DOCUMENT
    );

    render(<GuidePage />);
    await screen.findByText('a dungeon stone wall');

    expect(screen.getByText('Yes')).toBeInTheDocument();
    expect(screen.queryByText('on')).toBeNull();
  });

  it('marks the assumed answer differently from a chosen one', async () => {
    // The dashed outline says "this is what the parts are built from,
    // but nobody has said so" — `answerBorder`'s middle arm, which
    // was removable green.
    visit('?guide=wall&method=separate-wall');
    mockFetch((url) =>
      url.includes('/resolve')
        ? {
            ...RESOLVED_WITH_PARTS,
            refinements: RESOLVED_WITH_PARTS.refinements.map((r) =>
              r.key === 'texture'
                ? {
                    ...r,
                    recommended: 'texture|dungeon_stone',
                    choices: [
                      { tag: 'texture|dungeon_stone', title: 'Dungeon stone' },
                      { tag: 'texture|cave', title: 'Cave' },
                    ],
                  }
                : r
            ),
          }
        : GUIDE_DOCUMENT
    );

    render(<GuidePage />);
    // Scoped to the wall texture: the floor texture offers a Dungeon
    // stone of its own, and only this one has a recommendation.
    const texture = await screen.findByRole('group', { name: 'Texture' });
    const assumed = within(texture).getByRole('button', {
      name: /Dungeon stone/,
    });

    expect(assumed.className).toContain('border-dashed');
    expect(
      within(texture).getByRole('button', { name: 'Cave' }).className
    ).not.toContain('border-dashed');
  });

  it('never explains away the answer you actually gave', async () => {
    // An answer can be in the dead set and still be the selection —
    // availability describes what the catalog has, not what the URL
    // says. The chosen answer is always drawn, so listing it under
    // "no Wall" as well would have the page contradict itself about
    // the one thing the person definitely chose.
    visit('?guide=wall&method=separate-wall&texture=texture|cave');
    global.fetch = jest.fn((url: string) => {
      const body = url.includes('/availability')
        ? {
            unavailable: { texture: ['texture|cave'] },
            because: { texture: { 'texture|cave': { part: 'Wall' } } },
            options: {},
          }
        : url.includes('/resolve')
          ? {
              ...RESOLVED_WITH_PARTS,
              refinements: RESOLVED_WITH_PARTS.refinements.map((r) =>
                r.key === 'texture'
                  ? {
                      ...r,
                      selected: 'texture|cave',
                      choices: [
                        { tag: 'texture|dungeon_stone', title: 'Dungeon stone' },
                        { tag: 'texture|cave', title: 'Cave' },
                      ],
                    }
                  : r
              ),
            }
          : GUIDE_DOCUMENT;
      return Promise.resolve({
        ok: true,
        status: 200,
        json: () => Promise.resolve(body),
      });
    }) as unknown as typeof fetch;

    render(<GuidePage />);
    await screen.findByText('a dungeon stone wall');
    // Reopen the settled texture question, which is where the list
    // and its "missing" note are drawn together. By the collapsed
    // control, not by its label — the floor texture offers a Cave too.
    const folded = screen
      .getAllByRole('button', { name: /Cave/ })
      .find((b) => b.getAttribute('aria-expanded') === 'false')!;
    fireEvent.click(folded);

    await waitFor(() => expect(screen.queryByText(/Cave — no Wall/)).toBeNull());
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
