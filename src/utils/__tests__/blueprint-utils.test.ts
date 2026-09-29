import { downloadFiles, shouldShowDownloadLink, collectDownloadUrls, getLatestModificationDate } from '../blueprint-utils';
import { createMockBlueprint } from '@/test-utils';
import { Blueprint } from '@/types';

describe('blueprint-utils', () => {
  describe('downloadFiles', () => {
    /**
     * `redirect: 'manual'` stops at the 302 and hands back an opaque response:
     * no status, no headers. That is the success signal — the server had
     * somewhere to send us.
     */
    const redirected = { type: 'opaqueredirect', ok: false } as Response;

    beforeEach(() => {
      jest.useFakeTimers();
      global.fetch = jest.fn().mockResolvedValue(redirected);
      document.body.innerHTML = '';
    });

    afterEach(() => {
      jest.useRealTimers();
      jest.restoreAllMocks();
    });

    const iframes = () => document.body.querySelectorAll('iframe');

    it('navigates for a single URL, with no iframe and no probe', async () => {
      const nav = jest.fn();

      const outcome = await downloadFiles(['/api/blueprints/1/download'], nav);

      expect(nav).toHaveBeenCalledWith('/api/blueprints/1/download');
      expect(iframes()).toHaveLength(0);
      expect(global.fetch).not.toHaveBeenCalled();
      expect(outcome).toEqual({
        started: ['/api/blueprints/1/download'],
        failed: [],
      });
    });

    it('hands every file to the browser and says which', async () => {
      const outcome = await downloadFiles(['/a', '/b'], jest.fn());

      expect(iframes()).toHaveLength(2);
      expect(outcome).toEqual({ started: ['/a', '/b'], failed: [] });
    });

    it('leaves each iframe up long enough for the download to start', async () => {
      // The regression this file previously enforced: it asserted removeChild
      // had been called, so a teardown that aborted the request was the
      // expected behaviour. Removing an iframe whose request has not begun
      // transferring aborts it (NS_BINDING_ABORTED in Firefox), and the
      // /download redirect alone measured 5.03s on a cold Lambda against the
      // old 1000ms budget.
      await downloadFiles(['/a', '/b'], jest.fn());

      jest.advanceTimersByTime(6_000);
      expect(iframes()).toHaveLength(2);

      jest.advanceTimersByTime(60_000);
      expect(iframes()).toHaveLength(0);
    });

    it('reports a file it could not presign, and starts nothing for it', async () => {
      (global.fetch as jest.Mock)
        .mockResolvedValueOnce(redirected)
        .mockResolvedValueOnce({ type: 'basic', ok: false, status: 500 });

      const outcome = await downloadFiles(['/a', '/b'], jest.fn());

      expect(outcome).toEqual({ started: ['/a'], failed: ['/b'] });
      expect(iframes()).toHaveLength(1);
    });

    it('treats a network failure as a failed file rather than throwing', async () => {
      (global.fetch as jest.Mock).mockRejectedValue(new Error('offline'));

      const outcome = await downloadFiles(['/a', '/b'], jest.fn());

      expect(outcome).toEqual({ started: [], failed: ['/a', '/b'] });
      expect(iframes()).toHaveLength(0);
    });

    it('returns an empty outcome for no urls', async () => {
      await expect(downloadFiles([], jest.fn())).resolves.toEqual({
        started: [],
        failed: [],
      });
      expect(global.fetch).not.toHaveBeenCalled();
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
