import {
  GuideBlueprint,
  GuideDocument,
  fetchGuide,
  fetchGuides,
  resolveGuide,
  selectionKeys,
  thumbnailOf,
} from '../guide-service';

/**
 * The service is five pure-ish async functions, so they are tested
 * directly rather than through a render. Several of these branches are
 * invisible from the page: `GuideList` shows the same text whether the
 * list is empty or the request failed, so a component test cannot tell
 * the 404 path from the catch.
 */

/**
 * `json()` returns a promise in a real Response, and the service calls
 * `.catch()` on it, so the stub has to as well — a stub that returns a
 * bare value passes the happy path and breaks only on the error paths
 * these tests exist for.
 */
function respondWith(
  response: Omit<Partial<Response>, 'json'> & { json?: () => unknown }
) {
  const { json, ...rest } = response;
  global.fetch = jest.fn(() =>
    Promise.resolve({
      ...rest,
      json: json
        ? () => Promise.resolve().then(json)
        : () => Promise.reject(new Error('no body')),
    })
  ) as unknown as typeof fetch;
}

const DOCUMENT: GuideDocument = {
  key: 'wall',
  title: 'How do I make a wall?',
  steps: [
    { key: 'method', prompt: 'How?', options: [] },
    { key: 'width', prompt: 'How wide?', options: [] },
  ],
  refinements: [{ key: 'texture' }],
  roles: {},
};

describe('fetchGuides', () => {
  it('reads an empty catalog from the 404 this API answers with', async () => {
    // House convention (openforge/CLAUDE.md): an empty collection is a
    // 404, not a 200 with []. Treating it as an error would make an
    // empty catalog indistinguishable from a broken one.
    respondWith({ ok: false, status: 404, json: () => ({ guides: [] }) });

    await expect(fetchGuides()).resolves.toEqual([]);
  });

  it('throws on any other failure', async () => {
    respondWith({ ok: false, status: 500, statusText: 'Server Error' });

    await expect(fetchGuides()).rejects.toThrow('Server Error');
  });

  it('returns the guides on success', async () => {
    respondWith({
      ok: true,
      status: 200,
      json: () => ({ guides: [{ guide_key: 'wall', title: 'W', summary: null }] }),
    });

    await expect(fetchGuides()).resolves.toEqual([
      { guide_key: 'wall', title: 'W', summary: null },
    ]);
  });
});

describe('fetchGuide', () => {
  it('throws rather than resolving undefined when the guide is gone', async () => {
    // Silently resolving would leave the page waiting for a document
    // that never arrives, showing its heading and nothing else.
    respondWith({ ok: false, status: 404, statusText: 'Not Found' });

    await expect(fetchGuide('nonesuch')).rejects.toThrow('Not Found');
  });

  it('encodes the key into the path', async () => {
    respondWith({ ok: true, status: 200, json: () => ({ document: DOCUMENT }) });

    await fetchGuide('a wall/x');

    expect(global.fetch).toHaveBeenCalledWith('/api/guides/a%20wall%2Fx');
  });
});

describe('selectionKeys', () => {
  it('is every step key and every refinement key', () => {
    expect(selectionKeys(DOCUMENT)).toEqual(
      new Set(['method', 'width', 'texture'])
    );
  });

  it('copes with a guide that defines no refinements', () => {
    const { refinements, ...withoutRefinements } = DOCUMENT;
    void refinements;

    expect(selectionKeys(withoutRefinements)).toEqual(
      new Set(['method', 'width'])
    );
  });
});

describe('resolveGuide', () => {
  it('is a GET with the selections in the query string', async () => {
    respondWith({ ok: true, status: 200, json: () => ({}) });

    await resolveGuide('wall', { method: 's2w', texture: 'texture|cave' });

    // One argument: no method, no headers, no body. A POST here would
    // be a different endpoint.
    expect(global.fetch).toHaveBeenCalledWith(
      '/api/guides/wall/resolve?method=s2w&texture=texture%7Ccave'
    );
    expect((global.fetch as jest.Mock).mock.calls[0]).toHaveLength(1);
  });

  it('asks without a query string when nothing is selected', async () => {
    respondWith({ ok: true, status: 200, json: () => ({}) });

    await resolveGuide('wall', {});

    expect(global.fetch).toHaveBeenCalledWith('/api/guides/wall/resolve');
  });

  it("carries the API's own message out of a 400", async () => {
    // The 400 body says which selection is wrong; the status text does
    // not. A stale shared link is the common case and the person can
    // only act on the specific message.
    respondWith({
      ok: false,
      status: 400,
      statusText: 'Bad Request',
      json: () => ({ error: "step 'method' has no option 'nonesuch'" }),
    });

    await expect(resolveGuide('wall', { method: 'nonesuch' })).rejects.toThrow(
      "step 'method' has no option 'nonesuch'"
    );
  });

  it('falls back to the status when the body is not JSON', async () => {
    respondWith({
      ok: false,
      status: 502,
      statusText: 'Bad Gateway',
      json: () => {
        throw new Error('not json');
      },
    });

    await expect(resolveGuide('wall', {})).rejects.toThrow('Bad Gateway');
  });
});

describe('thumbnailOf', () => {
  const withImages = (
    images: GuideBlueprint['images']
  ): GuideBlueprint => ({
    id: 'bp-1',
    blueprint_name: 'a wall',
    file_md5: null,
    storage_address: null,
    images,
  });

  it('picks the thumbnail, not the first image', () => {
    const blueprint = withImages([
      {
        id: '1',
        image_name: 'a diagram',
        image_url: 'doc.png',
        image_type: 'documentation',
      },
      {
        id: '2',
        image_name: 'b render',
        image_url: 'thumb.png',
        image_type: 'thumbnail',
      },
    ]);

    expect(thumbnailOf(blueprint)?.image_url).toBe('thumb.png');
  });

  it('shows nothing rather than a documentation image', () => {
    const blueprint = withImages([
      {
        id: '1',
        image_name: 'a diagram',
        image_url: 'doc.png',
        image_type: 'documentation',
      },
    ]);

    expect(thumbnailOf(blueprint)).toBeNull();
  });

  it('copes with a part that resolved to nothing', () => {
    expect(thumbnailOf(null)).toBeNull();
    expect(thumbnailOf(withImages(undefined))).toBeNull();
    expect(thumbnailOf(withImages([]))).toBeNull();
  });
});
