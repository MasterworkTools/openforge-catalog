import { downloadFiles, shouldShowDownloadLink, collectDownloadUrls, getLatestModificationDate } from '../blueprint-utils';
import { createMockBlueprint } from '@/test-utils';
import { Blueprint } from '@/types';

describe('blueprint-utils', () => {
  describe('downloadFiles', () => {
    beforeEach(() => {
      jest.useFakeTimers();
      global.fetch = jest.fn();
      document.body.innerHTML = '';
    });

    afterEach(() => {
      jest.useRealTimers();
      jest.restoreAllMocks();
      window.location.hash = '';
    });

    const iframes = () => Array.from(document.body.querySelectorAll('iframe'));

    /**
     * Give a frame a real same-origin Document with `text` as its body, which is
     * what a browser hands back when the response rendered instead of
     * downloading. A real Document rather than an object literal so the stub
     * cannot drift from the shape the code reads.
     */
    const withDocument = (frame: HTMLIFrameElement, text: string) =>
      withRenderedBody(frame, (body) => {
        body.textContent = text;
      });

    /** As `withDocument`, but the body is real markup rather than flat text. */
    const withMarkup = (frame: HTMLIFrameElement, markup: string) =>
      withRenderedBody(frame, (body) => {
        body.innerHTML = markup;
      });

    const withRenderedBody = (frame: HTMLIFrameElement, fill: (body: HTMLElement) => void) => {
      const doc = document.implementation.createHTMLDocument('');
      fill(doc.body);
      Object.defineProperty(frame, 'contentDocument', { configurable: true, get: () => doc });
      return frame;
    };
    const sources = () => iframes().map((frame) => frame.getAttribute('src'));

    it('navigates for a single URL, creating no iframe', () => {
      const nav = jest.fn();

      downloadFiles(['/api/blueprints/1/download'], nav);

      expect(nav).toHaveBeenCalledTimes(1);
      expect(nav).toHaveBeenCalledWith('/api/blueprints/1/download');
      expect(iframes()).toHaveLength(0);
      expect(global.fetch).not.toHaveBeenCalled();
    });

    it('uses window.location when no nav is given', () => {
      // jsdom refuses document navigation, which is why `location` and its
      // `href` accessor cannot be replaced — but it implements hash navigation,
      // so the default argument can be pinned without touching the environment
      // or reshaping the function.
      downloadFiles(['#dl-marker']);

      expect(window.location.hash).toBe('#dl-marker');
    });

    it('points one hidden iframe at each URL', () => {
      const nav = jest.fn();

      downloadFiles(['/a', '/b'], nav);

      // The src is the download request. Asserting only the iframe count lets a
      // version that creates two empty iframes pass, which would download
      // nothing at all.
      expect(sources()).toEqual(['/a', '/b']);
      expect(iframes().map((frame) => frame.style.display)).toEqual(['none', 'none']);
      // Navigating during a batch would cancel the requests just issued, which
      // is the original bug by another route.
      expect(nav).not.toHaveBeenCalled();
    });

    it('leaves each iframe up long enough for the download to start', () => {
      // The regression this file previously enforced: it asserted removeChild
      // had been called, so a teardown that aborted the request was the
      // expected behaviour. Removing an iframe whose request has not begun
      // transferring aborts it (NS_BINDING_ABORTED in Firefox), and the
      // /download redirect alone measured ~4.7s on a cold Lambda against the
      // old 1000ms budget.
      downloadFiles(['/a', '/b'], jest.fn());

      jest.advanceTimersByTime(6_000);
      expect(iframes()).toHaveLength(2);

      jest.advanceTimersByTime(60_000);
      expect(iframes()).toHaveLength(0);
    });

    it('issues no request of its own, so a download is never gated on a pre-flight', () => {
      // An earlier version of this fix probed each URL with `redirect: 'manual'`
      // before creating its iframe. Measurement killed it: the 60s lifetime
      // already absorbs the cold start the probe was meant to hide, and a probe
      // that failed for any reason skipped a download that would have worked.
      downloadFiles(['/a', '/b'], jest.fn());

      expect(global.fetch).not.toHaveBeenCalled();
      expect(sources()).toEqual(['/a', '/b']);
    });

    it('warns when a download produced a page instead of a file', () => {
      // The R2-refusal class: a valid 302 whose object is gone. Cross-origin, so
      // the error page is unreadable and `contentDocument` is null — which is the
      // signal. jsdom has no cross-origin, so the null is supplied here.
      const warn = jest.spyOn(console, 'warn').mockImplementation(() => {});
      const readable = Object.getOwnPropertyDescriptor(
        HTMLIFrameElement.prototype,
        'contentDocument'
      );
      Object.defineProperty(HTMLIFrameElement.prototype, 'contentDocument', {
        configurable: true,
        get: () => null,
      });

      try {
        downloadFiles(['/a', '/b'], jest.fn());
        iframes().forEach((frame) => frame.dispatchEvent(new Event('load')));
      } finally {
        if (readable) {
          Object.defineProperty(HTMLIFrameElement.prototype, 'contentDocument', readable);
        }
      }

      expect(warn).toHaveBeenCalledTimes(2);
      expect(warn.mock.calls[0][1]).toBe('/a');
      expect(warn.mock.calls[0][2]).toBe('(cross-origin)');
      expect(warn.mock.calls[1][1]).toBe('/b');
    });

    it("warns with the API's own error text when the failure is same-origin", () => {
      // Reachable, not hypothetical: _get_signed_urls bare-returns when
      // storage_address is NULL, and collectDownloadUrls never screens that
      // field. Same-origin, so the body is readable and worth printing.
      const warn = jest.spyOn(console, 'warn').mockImplementation(() => {});

      // `download_blueprint` uses a bare `abort(404)`, so what actually renders is
      // Werkzeug's HTML page rather than JSON. Set as real markup, not as flat
      // text: with a markup-free fixture `innerHTML` and `textContent` are equal,
      // so a version reading markup instead of text would pass here and then warn
      // on a successful download whose blank page is styled rather than empty.
      const markup =
        '<h1>Not Found</h1><p>The requested URL was not found on the server. If' +
        ' you entered the URL manually please check your spelling and try again.</p>';
      const rendered =
        'Not FoundThe requested URL was not found on the server. If you entered' +
        ' the URL manually please check your spelling and try again.';

      downloadFiles(['/a', '/b'], jest.fn());
      withMarkup(iframes()[0], markup).dispatchEvent(new Event('load'));

      expect(warn).toHaveBeenCalledWith('download did not start:', '/a', rendered);
    });

    it('stays quiet when the download succeeded', () => {
      // A download never commits a document, so the frame keeps the readable,
      // EMPTY about:blank it inherited — body present, textContent ''. That is
      // the shape to pin: jsdom never loads the src, so a frame left as-is has
      // no body at all, which is a different state and would test the bodyless
      // fallback instead of success. Warning on `load` alone, or on a readable
      // empty body, would fire on every Firefox download.
      const warn = jest.spyOn(console, 'warn').mockImplementation(() => {});

      downloadFiles(['/a', '/b'], jest.fn());
      iframes().forEach((frame) => {
        // Not decoration: a sandboxed frame is an opaque origin, so
        // `contentDocument` would read null and every success would warn. This is
        // the executable form of the caveat on the listener.
        expect(frame.hasAttribute('sandbox')).toBe(false);
        const blank = withDocument(frame, '');
        expect(blank.contentDocument!.body.textContent).toBe('');
        blank.dispatchEvent(new Event('load'));
      });

      expect(warn).not.toHaveBeenCalled();
    });

    it('stays quiet for a whitespace-only body, and truncates a long one', () => {
      const warn = jest.spyOn(console, 'warn').mockImplementation(() => {});

      downloadFiles(['/a', '/b'], jest.fn());
      withDocument(iframes()[0], '   \n  ').dispatchEvent(new Event('load'));
      expect(warn).not.toHaveBeenCalled();

      // Distinguishable head and tail, so this pins *which* 200 characters:
      // a repeated character leaves slice(-200) passing.
      const long = 'A'.repeat(200) + 'B'.repeat(300);
      withDocument(iframes()[1], long).dispatchEvent(new Event('load'));
      expect(warn).toHaveBeenCalledWith('download did not start:', '/b', 'A'.repeat(200));
    });

    it('stays quiet for a document that has no body yet', () => {
      // Distinct from both success and failure: a frame whose document exists
      // but has not parsed a body is not evidence of anything.
      const warn = jest.spyOn(console, 'warn').mockImplementation(() => {});

      downloadFiles(['/a', '/b'], jest.fn());
      const frame = iframes()[0];
      // jsdom never loads the src, so this frame is already in that state — no
      // stub needed, and none wanted.
      expect(frame.contentDocument!.body).toBeNull();
      frame.dispatchEvent(new Event('load'));

      expect(warn).not.toHaveBeenCalled();
    });

    it('does nothing for no urls', () => {
      const nav = jest.fn();

      downloadFiles([], nav);

      expect(iframes()).toHaveLength(0);
      expect(global.fetch).not.toHaveBeenCalled();
      expect(nav).not.toHaveBeenCalled();
    });
  });

  describe('shouldShowDownloadLink', () => {
    const mockBlueprint = createMockBlueprint();

    it('returns true when blueprint has file_name', () => {
      const result = shouldShowDownloadLink(mockBlueprint, {});
      expect(result).toBe(true);
    });

    it('returns false when blueprint has no file_name and no config parts', () => {
      const blueprintWithoutFile = createMockBlueprint({ file_name: '' });
      const result = shouldShowDownloadLink(blueprintWithoutFile, {});
      expect(result).toBe(false);
    });

    it('returns true when all required parts are selected', () => {
      const blueprintWithConfig = createMockBlueprint({
        file_name: '',
        blueprint_config: {
          parts: [
            {
              name: 'part1',
              tags: { require: [{ tag: 'required_tag' }], deny: [], accept: [], constrain: [] }
            }
          ]
        }
      });
      const configSelections = {
        part1: createMockBlueprint({ id: '2' })
      };
      const result = shouldShowDownloadLink(blueprintWithConfig, configSelections);
      expect(result).toBe(true);
    });

    it('handles 2 levels of nesting correctly', () => {
      const blueprintWithConfig = createMockBlueprint({
        file_name: '',
        blueprint_config: {
          parts: [
            {
              name: 'parentPart',
              tags: { require: [{ tag: 'required_tag' }], deny: [], accept: [], constrain: [] }
            }
          ]
        }
      });

      const childBlueprint = createMockBlueprint({
        id: '2',
        blueprint_config: {
          parts: [
            {
              name: 'childPart',
              tags: { require: [{ tag: 'required_tag' }], deny: [], accept: [], constrain: [] }
            }
          ]
        }
      });

      const configSelections = {
        parentPart: childBlueprint,
        'parentPart|childPart': createMockBlueprint({ id: '3' })
      };

      const result = shouldShowDownloadLink(blueprintWithConfig, configSelections);
      expect(result).toBe(true);
    });

    it('handles 3 levels of nesting correctly', () => {
      const blueprintWithConfig = createMockBlueprint({
        file_name: '',
        blueprint_config: {
          parts: [
            {
              name: 'level1',
              tags: { require: [{ tag: 'required_tag' }], deny: [], accept: [], constrain: [] }
            }
          ]
        }
      });

      const level2Blueprint = createMockBlueprint({
        id: '2',
        blueprint_config: {
          parts: [
            {
              name: 'level2',
              tags: { require: [{ tag: 'required_tag' }], deny: [], accept: [], constrain: [] }
            }
          ]
        }
      });

      const level3Blueprint = createMockBlueprint({
        id: '3',
        blueprint_config: {
          parts: [
            {
              name: 'level3',
              tags: { require: [{ tag: 'required_tag' }], deny: [], accept: [], constrain: [] }
            }
          ]
        }
      });

      const configSelections = {
        level1: level2Blueprint,
        'level1|level2': level3Blueprint,
        'level1|level2|level3': createMockBlueprint({ id: '4' })
      };

      const result = shouldShowDownloadLink(blueprintWithConfig, configSelections);
      expect(result).toBe(true);
    });

    it('returns false when nested required parts are missing', () => {
      const blueprintWithConfig = createMockBlueprint({
        file_name: '',
        blueprint_config: {
          parts: [
            {
              name: 'parentPart',
              tags: { require: [{ tag: 'required_tag' }], deny: [], accept: [], constrain: [] }
            }
          ]
        }
      });

      const childBlueprint = createMockBlueprint({
        id: '2',
        blueprint_config: {
          parts: [
            {
              name: 'childPart',
              tags: { require: [{ tag: 'required_tag' }], deny: [], accept: [], constrain: [] }
            }
          ]
        }
      });

      // Missing the nested child part selection
      const configSelections = {
        parentPart: childBlueprint
        // Missing: 'parentPart|childPart'
      };

      const result = shouldShowDownloadLink(blueprintWithConfig, configSelections);
      expect(result).toBe(false);
    });

    it('returns true for blueprints with file_name', () => {
      const blueprint: Blueprint = {
        id: 'test-id',
        blueprint_name: 'Test Blueprint',
        blueprint_type: 'model',
        file_name: 'test.stl',
        file_md5: 'test-md5',
        file_size: 1000,
        full_name: 'Test Blueprint',
        created_at: '2023-01-01T00:00:00Z',
        file_modified_at: '2023-01-01T00:00:00Z',
        signed_url: 'test-url',
        storage_address: 'test-address',
        tags: [],
        images: [],
        updated_at: '2023-01-01T00:00:00Z'
      };

      const result = shouldShowDownloadLink(blueprint, {});
      expect(result).toBe(true);
    });

    it('returns false for blueprints without file_name and no config', () => {
      const blueprint: Blueprint = {
        id: 'test-id',
        blueprint_name: 'Test Blueprint',
        blueprint_type: 'blueprint',
        file_name: '',
        file_md5: 'test-md5',
        file_size: 1000,
        full_name: 'Test Blueprint',
        created_at: '2023-01-01T00:00:00Z',
        file_modified_at: '2023-01-01T00:00:00Z',
        signed_url: 'test-url',
        storage_address: 'test-address',
        tags: [],
        images: [],
        updated_at: '2023-01-01T00:00:00Z'
      };

      const result = shouldShowDownloadLink(blueprint, {});
      expect(result).toBe(false);
    });

    it('returns true when all required parts are selected', () => {
      const blueprint: Blueprint = {
        id: 'test-id',
        blueprint_name: 'Test Blueprint',
        blueprint_type: 'blueprint',
        file_name: '',
        file_md5: 'test-md5',
        file_size: 1000,
        full_name: 'Test Blueprint',
        created_at: '2023-01-01T00:00:00Z',
        file_modified_at: '2023-01-01T00:00:00Z',
        signed_url: 'test-url',
        storage_address: 'test-address',
        tags: [],
        images: [],
        updated_at: '2023-01-01T00:00:00Z',
        blueprint_config: {
          parts: [
            {
              name: 'wall',
              tags: {
                require: [{ tag: 'shape|wall' }]
              }
            }
          ]
        }
      };

      const configSelections = {
        'wall': {
          id: 'wall-id',
          blueprint_name: 'Wall Part',
          blueprint_type: 'model',
          file_name: 'wall.stl',
          file_md5: 'wall-md5',
          file_size: 500,
          full_name: 'Wall Part',
          created_at: '2023-01-01T00:00:00Z',
          file_modified_at: '2023-01-01T00:00:00Z',
          signed_url: 'wall-url',
          storage_address: 'wall-address',
          tags: ['shape|wall'],
          images: [],
          updated_at: '2023-01-01T00:00:00Z'
        }
      };

      const result = shouldShowDownloadLink(blueprint, configSelections);
      expect(result).toBe(true);
    });

    it('returns false when required parts are not selected', () => {
      const blueprint: Blueprint = {
        id: 'test-id',
        blueprint_name: 'Test Blueprint',
        blueprint_type: 'blueprint',
        file_name: '',
        file_md5: 'test-md5',
        file_size: 1000,
        full_name: 'Test Blueprint',
        created_at: '2023-01-01T00:00:00Z',
        file_modified_at: '2023-01-01T00:00:00Z',
        signed_url: 'test-url',
        storage_address: 'test-address',
        tags: [],
        images: [],
        updated_at: '2023-01-01T00:00:00Z',
        blueprint_config: {
          parts: [
            {
              name: 'wall',
              tags: {
                require: [{ tag: 'shape|wall' }]
              }
            }
          ]
        }
      };

      const result = shouldShowDownloadLink(blueprint, {});
      expect(result).toBe(false);
    });

    it('ignores optional parts when determining download availability', () => {
      const blueprint: Blueprint = {
        id: 'test-id',
        blueprint_name: 'Test Blueprint',
        blueprint_type: 'blueprint',
        file_name: '',
        file_md5: 'test-md5',
        file_size: 1000,
        full_name: 'Test Blueprint',
        created_at: '2023-01-01T00:00:00Z',
        file_modified_at: '2023-01-01T00:00:00Z',
        signed_url: 'test-url',
        storage_address: 'test-address',
        tags: [],
        images: [],
        updated_at: '2023-01-01T00:00:00Z',
        blueprint_config: {
          parts: [
            {
              name: 'wall',
              tags: {
                require: [{ tag: 'shape|wall' }]
              }
            },
            {
              name: 'decoration',
              optional: true,
              tags: {
                require: [{ tag: 'shape|decoration' }]
              }
            }
          ]
        }
      };

      const configSelections = {
        'wall': {
          id: 'wall-id',
          blueprint_name: 'Wall Part',
          blueprint_type: 'model',
          file_name: 'wall.stl',
          file_md5: 'wall-md5',
          file_size: 500,
          full_name: 'Wall Part',
          created_at: '2023-01-01T00:00:00Z',
          file_modified_at: '2023-01-01T00:00:00Z',
          signed_url: 'wall-url',
          storage_address: 'wall-address',
          tags: ['shape|wall'],
          images: [],
          updated_at: '2023-01-01T00:00:00Z'
        }
        // Note: decoration is not selected but it's optional, so download should still be available
      };

      const result = shouldShowDownloadLink(blueprint, configSelections);
      expect(result).toBe(true);
    });

    it('requires optional parts to be selected if they have require tags', () => {
      const blueprint: Blueprint = {
        id: 'test-id',
        blueprint_name: 'Test Blueprint',
        blueprint_type: 'blueprint',
        file_name: '',
        file_md5: 'test-md5',
        file_size: 1000,
        full_name: 'Test Blueprint',
        created_at: '2023-01-01T00:00:00Z',
        file_modified_at: '2023-01-01T00:00:00Z',
        signed_url: 'test-url',
        storage_address: 'test-address',
        tags: [],
        images: [],
        updated_at: '2023-01-01T00:00:00Z',
        blueprint_config: {
          parts: [
            {
              name: 'wall',
              tags: {
                require: [{ tag: 'shape|wall' }]
              }
            },
            {
              name: 'decoration',
              optional: true,
              tags: {
                require: [{ tag: 'shape|decoration' }]
              }
            }
          ]
        }
      };

      const configSelections = {
        'wall': {
          id: 'wall-id',
          blueprint_name: 'Wall Part',
          blueprint_type: 'model',
          file_name: 'wall.stl',
          file_md5: 'wall-md5',
          file_size: 500,
          full_name: 'Wall Part',
          created_at: '2023-01-01T00:00:00Z',
          file_modified_at: '2023-01-01T00:00:00Z',
          signed_url: 'wall-url',
          storage_address: 'wall-address',
          tags: ['shape|wall'],
          images: [],
          updated_at: '2023-01-01T00:00:00Z'
        },
        'decoration': {
          id: 'decoration-id',
          blueprint_name: 'Decoration Part',
          blueprint_type: 'model',
          file_name: 'decoration.stl',
          file_md5: 'decoration-md5',
          file_size: 200,
          full_name: 'Decoration Part',
          created_at: '2023-01-01T00:00:00Z',
          file_modified_at: '2023-01-01T00:00:00Z',
          signed_url: 'decoration-url',
          storage_address: 'decoration-address',
          tags: ['shape|decoration'],
          images: [],
          updated_at: '2023-01-01T00:00:00Z'
        }
      };

      const result = shouldShowDownloadLink(blueprint, configSelections);
      expect(result).toBe(true);
    });
  });

  describe('collectDownloadUrls', () => {
    const mockBlueprint = createMockBlueprint();

    it('includes main blueprint URL when it has file_name', () => {
      const urls = collectDownloadUrls(mockBlueprint, {});
      expect(urls).toContain('/api/blueprints/1/download');
    });

    it('includes URLs for selected parts', () => {
      const configSelections = {
        part1: createMockBlueprint({ id: '2', file_name: 'part1.stl' })
      };
      const urls = collectDownloadUrls(mockBlueprint, configSelections);
      expect(urls).toContain('/api/blueprints/1/download');
      expect(urls).toContain('/api/blueprints/2/download');
    });

    it('does not include duplicate URLs', () => {
      const configSelections = {
        part1: createMockBlueprint({ id: '1', file_name: 'part1.stl' })
      };
      const urls = collectDownloadUrls(mockBlueprint, configSelections);
      expect(urls).toEqual(['/api/blueprints/1/download']);
    });
  });

  describe('getLatestModificationDate', () => {
    it('returns the file_modified_at date', () => {
      const blueprint = createMockBlueprint({
        file_modified_at: '2023-01-02T00:00:00Z'
      });

      const result = getLatestModificationDate(blueprint);
      expect(result).toEqual(new Date('2023-01-02T00:00:00Z'));
    });
  });
});
