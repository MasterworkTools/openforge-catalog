import { downloadFiles, shouldShowDownloadLink, collectDownloadUrls, getLatestModificationDate } from '../blueprint-utils';
import { createMockBlueprint } from '@/test-utils';
import { Blueprint } from '@/types';

describe('blueprint-utils', () => {
  describe('downloadFiles', () => {
    let createElementSpy: jest.SpyInstance;
    let appendChildSpy: jest.SpyInstance;
    let removeChildSpy: jest.SpyInstance;
    let setTimeoutSpy: jest.SpyInstance;

    beforeEach(() => {
      createElementSpy = jest.spyOn(document, 'createElement').mockImplementation((tag: string) => {
        const el = document.createElementNS('http://www.w3.org/1999/xhtml', tag);
        // @ts-expect-error - Mocking style property for test
        el.style = {};
        return el;
      });
      appendChildSpy = jest.spyOn(document.body, 'appendChild').mockImplementation((node: Node) => node);
      removeChildSpy = jest.spyOn(document.body, 'removeChild').mockImplementation((node: Node) => node);
      setTimeoutSpy = jest.spyOn(global, 'setTimeout').mockImplementation((fn: () => void) => {
        fn();
        return 1 as unknown as NodeJS.Timeout;
      });
    });

    afterEach(() => {
      createElementSpy.mockRestore();
      appendChildSpy.mockRestore();
      removeChildSpy.mockRestore();
      setTimeoutSpy.mockRestore();
    });

    it('calls nav for a single URL', async () => {
      const nav = jest.fn();
      await downloadFiles(['http://example.com/file1'], nav);
      expect(nav).toHaveBeenCalledWith('http://example.com/file1');
      expect(createElementSpy).not.toHaveBeenCalled();
    });

    it('downloads multiple files by creating iframes', async () => {
      const urls = ['http://example.com/file1', 'http://example.com/file2'];
      await downloadFiles(urls, jest.fn());
      expect(createElementSpy).toHaveBeenCalledTimes(2);
      expect(appendChildSpy).toHaveBeenCalledTimes(2);
      expect(removeChildSpy).toHaveBeenCalledTimes(2);
    });

    it('returns immediately for empty urls', async () => {
      await expect(downloadFiles([], jest.fn())).resolves.toBeUndefined();
      expect(createElementSpy).not.toHaveBeenCalled();
      expect(appendChildSpy).not.toHaveBeenCalled();
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
