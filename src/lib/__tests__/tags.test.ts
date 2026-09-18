import { getOtherBlueprintTags, getParentBlueprintTags, getSelectionsWithSamePrefix } from '../tags';

// Mock console.log to avoid noise in tests
const originalConsoleLog = console.log;
beforeAll(() => {
  console.log = jest.fn();
});

afterAll(() => {
  console.log = originalConsoleLog;
});

describe('tags.ts', () => {
  const mockBlueprint = {
    id: '123e4567-e89b-12d3-a456-426614174000',
    blueprint_name: 'Test Blueprint',
    blueprint_type: 'blueprint',
    blueprint_config: {},
    file_md5: 'test-md5',
    file_size: 1000,
    file_name: 'test.stl',
    full_name: 'Test Blueprint Full Name',
    file_modified_at: '2023-01-01T00:00:00Z',
    storage_address: 'test-address',
    signed_url: 'test-url',
    created_at: '2023-01-01T00:00:00Z',
    updated_at: '2023-01-01T00:00:00Z',
    tags: ['test', 'model', 'base'],
    images: []
  };

  const mockConfigSelections = {
    'part1': {
      id: 'part1-id',
      blueprint_name: 'Part 1',
      blueprint_type: 'blueprint',
      blueprint_config: {},
      file_md5: 'part1-md5',
      file_size: 1000,
      file_name: 'part1.stl',
      full_name: 'Part 1 Full Name',
      file_modified_at: '2023-01-01T00:00:00Z',
      storage_address: 'part1-address',
      signed_url: 'part1-url',
      created_at: '2023-01-01T00:00:00Z',
      updated_at: '2023-01-01T00:00:00Z',
      tags: ['part1', 'component'],
      images: []
    },
    'part1|subpart1': {
      id: 'subpart1-id',
      blueprint_name: 'Subpart 1',
      blueprint_type: 'blueprint',
      blueprint_config: {},
      file_md5: 'subpart1-md5',
      file_size: 1000,
      file_name: 'subpart1.stl',
      full_name: 'Subpart 1 Full Name',
      file_modified_at: '2023-01-01T00:00:00Z',
      storage_address: 'subpart1-address',
      signed_url: 'subpart1-url',
      created_at: '2023-01-01T00:00:00Z',
      updated_at: '2023-01-01T00:00:00Z',
      tags: ['subpart1', 'detail'],
      images: []
    },
    'part2': {
      id: 'part2-id',
      blueprint_name: 'Part 2',
      blueprint_type: 'blueprint',
      blueprint_config: {},
      file_md5: 'part2-md5',
      file_size: 1000,
      file_name: 'part2.stl',
      full_name: 'Part 2 Full Name',
      file_modified_at: '2023-01-01T00:00:00Z',
      storage_address: 'part2-address',
      signed_url: 'part2-url',
      created_at: '2023-01-01T00:00:00Z',
      updated_at: '2023-01-01T00:00:00Z',
      tags: ['part2', 'component'],
      images: []
    },
    'part1|subpart2': {
      id: 'subpart2-id',
      blueprint_name: 'Subpart 2',
      blueprint_type: 'blueprint',
      blueprint_config: {},
      file_md5: 'subpart2-md5',
      file_size: 1000,
      file_name: 'subpart2.stl',
      full_name: 'Subpart 2 Full Name',
      file_modified_at: '2023-01-01T00:00:00Z',
      storage_address: 'subpart2-address',
      signed_url: 'subpart2-url',
      created_at: '2023-01-01T00:00:00Z',
      updated_at: '2023-01-01T00:00:00Z',
      tags: ['subpart2', 'detail'],
      images: []
    }
  };

  describe('getParentBlueprintTags', () => {
    it('should return parent blueprint tags for nested parts', () => {
      const result = getParentBlueprintTags(mockConfigSelections, 'part1|subpart1', mockBlueprint);
      expect(result).toEqual(new Set(['part1', 'component']));
    });

    it('should return main blueprint tags for top-level parts', () => {
      const result = getParentBlueprintTags(mockConfigSelections, 'part1', mockBlueprint);
      expect(result).toEqual(new Set(['test', 'model', 'base']));
    });

    it('should handle parts without parent in configSelections', () => {
      const result = getParentBlueprintTags(mockConfigSelections, 'nonexistent|subpart', mockBlueprint);
      expect(result).toEqual(new Set());
    });

    it('should handle parent blueprint without tags', () => {
      const configSelectionsWithoutTags = {
        'part1': {
          id: 'part1-id',
          blueprint_name: 'Part 1',
          blueprint_type: 'blueprint',
          blueprint_config: {},
          file_md5: 'part1-md5',
          file_size: 1000,
          file_name: 'part1.stl',
          full_name: 'Part 1 Full Name',
          file_modified_at: '2023-01-01T00:00:00Z',
          storage_address: 'part1-address',
          signed_url: 'part1-url',
          created_at: '2023-01-01T00:00:00Z',
          updated_at: '2023-01-01T00:00:00Z',
          tags: [],
          images: []
        }
      };
      const result = getParentBlueprintTags(configSelectionsWithoutTags, 'part1|subpart1', mockBlueprint);
      expect(result).toEqual(new Set());
    });

    it('should handle main blueprint without tags', () => {
      const blueprintWithoutTags = {
        id: '123e4567-e89b-12d3-a456-426614174000',
        blueprint_name: 'Test Blueprint',
        blueprint_type: 'blueprint',
        blueprint_config: {},
        file_md5: 'test-md5',
        file_size: 1000,
        file_name: 'test.stl',
        full_name: 'Test Blueprint Full Name',
        file_modified_at: '2023-01-01T00:00:00Z',
        storage_address: 'test-address',
        signed_url: 'test-url',
        created_at: '2023-01-01T00:00:00Z',
        updated_at: '2023-01-01T00:00:00Z',
        tags: [],
        images: []
      };
      const result = getParentBlueprintTags(mockConfigSelections, 'part1', blueprintWithoutTags);
      expect(result).toEqual(new Set());
    });
  });

  describe('getSelectionsWithSamePrefix', () => {
    it('should return selections with same prefix for nested parts', () => {
      const result = getSelectionsWithSamePrefix(mockConfigSelections, 'part1|subpart1');
      expect(result).toEqual([
        ['part1', mockConfigSelections['part1']],
        ['part1|subpart1', mockConfigSelections['part1|subpart1']],
        ['part1|subpart2', mockConfigSelections['part1|subpart2']]
      ]);
    });

    it('should return only top-level selections for top-level parts', () => {
      const result = getSelectionsWithSamePrefix(mockConfigSelections, 'part1');
      expect(result).toEqual([
        ['part1', mockConfigSelections['part1']],
        ['part2', mockConfigSelections['part2']]
      ]);
    });

    it('should handle empty configSelections', () => {
      const result = getSelectionsWithSamePrefix({}, 'part1');
      expect(result).toEqual([]);
    });

    it('should handle parts with no prefix', () => {
      const result = getSelectionsWithSamePrefix(mockConfigSelections, 'standalone');
      expect(result).toEqual([
        ['part1', mockConfigSelections['part1']],
        ['part2', mockConfigSelections['part2']]
      ]);
    });

    it('should handle complex nested structures', () => {
      const complexSelections = {
        'level1': {
          id: 'level1-id',
          blueprint_name: 'Level 1',
          blueprint_type: 'blueprint',
          blueprint_config: {},
          file_md5: 'level1-md5',
          file_size: 1000,
          file_name: 'level1.stl',
          full_name: 'Level 1 Full Name',
          file_modified_at: '2023-01-01T00:00:00Z',
          storage_address: 'level1-address',
          signed_url: 'level1-url',
          created_at: '2023-01-01T00:00:00Z',
          updated_at: '2023-01-01T00:00:00Z',
          tags: ['level1'],
          images: []
        },
        'level1|level2': {
          id: 'level2-id',
          blueprint_name: 'Level 2',
          blueprint_type: 'blueprint',
          blueprint_config: {},
          file_md5: 'level2-md5',
          file_size: 1000,
          file_name: 'level2.stl',
          full_name: 'Level 2 Full Name',
          file_modified_at: '2023-01-01T00:00:00Z',
          storage_address: 'level2-address',
          signed_url: 'level2-url',
          created_at: '2023-01-01T00:00:00Z',
          updated_at: '2023-01-01T00:00:00Z',
          tags: ['level2'],
          images: []
        },
        'level1|level2|level3': {
          id: 'level3-id',
          blueprint_name: 'Level 3',
          blueprint_type: 'blueprint',
          blueprint_config: {},
          file_md5: 'level3-md5',
          file_size: 1000,
          file_name: 'level3.stl',
          full_name: 'Level 3 Full Name',
          file_modified_at: '2023-01-01T00:00:00Z',
          storage_address: 'level3-address',
          signed_url: 'level3-url',
          created_at: '2023-01-01T00:00:00Z',
          updated_at: '2023-01-01T00:00:00Z',
          tags: ['level3'],
          images: []
        },
        'other': {
          id: 'other-id',
          blueprint_name: 'Other',
          blueprint_type: 'blueprint',
          blueprint_config: {},
          file_md5: 'other-md5',
          file_size: 1000,
          file_name: 'other.stl',
          full_name: 'Other Full Name',
          file_modified_at: '2023-01-01T00:00:00Z',
          storage_address: 'other-address',
          signed_url: 'other-url',
          created_at: '2023-01-01T00:00:00Z',
          updated_at: '2023-01-01T00:00:00Z',
          tags: ['other'],
          images: []
        },
        'level1|other': {
          id: 'level1-other-id',
          blueprint_name: 'Level 1 Other',
          blueprint_type: 'blueprint',
          blueprint_config: {},
          file_md5: 'level1-other-md5',
          file_size: 1000,
          file_name: 'level1-other.stl',
          full_name: 'Level 1 Other Full Name',
          file_modified_at: '2023-01-01T00:00:00Z',
          storage_address: 'level1-other-address',
          signed_url: 'level1-other-url',
          created_at: '2023-01-01T00:00:00Z',
          updated_at: '2023-01-01T00:00:00Z',
          tags: ['other'],
          images: []
        }
      };

      const result = getSelectionsWithSamePrefix(complexSelections, 'level1|level2');
      expect(result).toEqual([
        ['level1', complexSelections['level1']],
        ['level1|level2', complexSelections['level1|level2']],
        ['level1|level2|level3', complexSelections['level1|level2|level3']],
        ['level1|other', complexSelections['level1|other']]
      ]);
    });
  });

  describe('getOtherBlueprintTags', () => {
    it('should combine parent and sibling tags for nested parts', () => {
      const result = getOtherBlueprintTags(mockConfigSelections, 'part1|subpart1', mockBlueprint);

      // Should include:
      // - Parent tags: ['part1', 'component'] (from getParentBlueprintTags)
      // - All sibling tags: ['part1', 'component'] (from part1), ['subpart1', 'detail'] (from part1|subpart1), ['subpart2', 'detail'] (from part1|subpart2)
      const expectedTags = new Set(['part1', 'component', 'subpart1', 'detail', 'subpart2', 'detail']);
      expect(result).toEqual(expectedTags);
    });

    it('should return main blueprint and sibling tags for top-level parts', () => {
      const result = getOtherBlueprintTags(mockConfigSelections, 'part1', mockBlueprint);

      // Should include:
      // - Main blueprint tags: ['test', 'model', 'base'] (from getParentBlueprintTags)
      // - All sibling tags: ['part1', 'component'] (from part1), ['part2', 'component'] (from part2)
      const expectedTags = new Set(['test', 'model', 'base', 'part1', 'component', 'part2', 'component']);
      expect(result).toEqual(expectedTags);
    });

    it('should handle empty configSelections', () => {
      const result = getOtherBlueprintTags({}, 'part1', mockBlueprint);
      expect(result).toEqual(new Set(['test', 'model', 'base']));
    });

    it('should handle parts with no siblings', () => {
      const singleSelection = {
        'part1': {
          id: 'part1-id',
          blueprint_name: 'Part 1',
          blueprint_type: 'blueprint',
          blueprint_config: {},
          file_md5: 'part1-md5',
          file_size: 1000,
          file_name: 'part1.stl',
          full_name: 'Part 1 Full Name',
          file_modified_at: '2023-01-01T00:00:00Z',
          storage_address: 'part1-address',
          signed_url: 'part1-url',
          created_at: '2023-01-01T00:00:00Z',
          updated_at: '2023-01-01T00:00:00Z',
          tags: ['part1', 'component'],
          images: []
        }
      };

      const result = getOtherBlueprintTags(singleSelection, 'part1', mockBlueprint);
      expect(result).toEqual(new Set(['test', 'model', 'base', 'part1', 'component']));
    });

    it('should handle blueprints without tags', () => {
      const blueprintWithoutTags = {
        id: '123e4567-e89b-12d3-a456-426614174000',
        blueprint_name: 'Test Blueprint',
        blueprint_type: 'blueprint',
        blueprint_config: {},
        file_md5: 'test-md5',
        file_size: 1000,
        file_name: 'test.stl',
        full_name: 'Test Blueprint Full Name',
        file_modified_at: '2023-01-01T00:00:00Z',
        storage_address: 'test-address',
        signed_url: 'test-url',
        created_at: '2023-01-01T00:00:00Z',
        updated_at: '2023-01-01T00:00:00Z',
        tags: [],
        images: []
      };

      const result = getOtherBlueprintTags(mockConfigSelections, 'part1', blueprintWithoutTags);
      expect(result).toEqual(new Set(['part1', 'component', 'part2', 'component']));
    });

    it('should handle configSelections with blueprints without tags', () => {
      const selectionsWithoutTags = {
        'part1': {
          id: 'part1-id',
          blueprint_name: 'Part 1',
          blueprint_type: 'blueprint',
          blueprint_config: {},
          file_md5: 'part1-md5',
          file_size: 1000,
          file_name: 'part1.stl',
          full_name: 'Part 1 Full Name',
          file_modified_at: '2023-01-01T00:00:00Z',
          storage_address: 'part1-address',
          signed_url: 'part1-url',
          created_at: '2023-01-01T00:00:00Z',
          updated_at: '2023-01-01T00:00:00Z',
          tags: [],
          images: []
        },
        'part2': {
          id: 'part2-id',
          blueprint_name: 'Part 2',
          blueprint_type: 'blueprint',
          blueprint_config: {},
          file_md5: 'part2-md5',
          file_size: 1000,
          file_name: 'part2.stl',
          full_name: 'Part 2 Full Name',
          file_modified_at: '2023-01-01T00:00:00Z',
          storage_address: 'part2-address',
          signed_url: 'part2-url',
          created_at: '2023-01-01T00:00:00Z',
          updated_at: '2023-01-01T00:00:00Z',
          tags: ['part2', 'component'],
          images: []
        }
      };

      const result = getOtherBlueprintTags(selectionsWithoutTags, 'part1', mockBlueprint);
      expect(result).toEqual(new Set(['test', 'model', 'base', 'part2', 'component']));
    });

    it('should handle complex nested structure with multiple levels', () => {
      const complexSelections = {
        'base': {
          id: 'base-id',
          blueprint_name: 'Base',
          blueprint_type: 'blueprint',
          blueprint_config: {},
          file_md5: 'base-md5',
          file_size: 1000,
          file_name: 'base.stl',
          full_name: 'Base Full Name',
          file_modified_at: '2023-01-01T00:00:00Z',
          storage_address: 'base-address',
          signed_url: 'base-url',
          created_at: '2023-01-01T00:00:00Z',
          updated_at: '2023-01-01T00:00:00Z',
          tags: ['base'],
          images: []
        },
        'base|level1': {
          id: 'level1-id',
          blueprint_name: 'Level 1',
          blueprint_type: 'blueprint',
          blueprint_config: {},
          file_md5: 'level1-md5',
          file_size: 1000,
          file_name: 'level1.stl',
          full_name: 'Level 1 Full Name',
          file_modified_at: '2023-01-01T00:00:00Z',
          storage_address: 'level1-address',
          signed_url: 'level1-url',
          created_at: '2023-01-01T00:00:00Z',
          updated_at: '2023-01-01T00:00:00Z',
          tags: ['level1'],
          images: []
        },
        'base|level1|level2': {
          id: 'level2-id',
          blueprint_name: 'Level 2',
          blueprint_type: 'blueprint',
          blueprint_config: {},
          file_md5: 'level2-md5',
          file_size: 1000,
          file_name: 'level2.stl',
          full_name: 'Level 2 Full Name',
          file_modified_at: '2023-01-01T00:00:00Z',
          storage_address: 'level2-address',
          signed_url: 'level2-url',
          created_at: '2023-01-01T00:00:00Z',
          updated_at: '2023-01-01T00:00:00Z',
          tags: ['level2'],
          images: []
        },
        'base|level1|level2|level3': {
          id: 'level3-id',
          blueprint_name: 'Level 3',
          blueprint_type: 'blueprint',
          blueprint_config: {},
          file_md5: 'level3-md5',
          file_size: 1000,
          file_name: 'level3.stl',
          full_name: 'Level 3 Full Name',
          file_modified_at: '2023-01-01T00:00:00Z',
          storage_address: 'level3-address',
          signed_url: 'level3-url',
          created_at: '2023-01-01T00:00:00Z',
          updated_at: '2023-01-01T00:00:00Z',
          tags: ['level3'],
          images: []
        },
        'base|other': {
          id: 'other-id',
          blueprint_name: 'Other',
          blueprint_type: 'blueprint',
          blueprint_config: {},
          file_md5: 'other-md5',
          file_size: 1000,
          file_name: 'other.stl',
          full_name: 'Other Full Name',
          file_modified_at: '2023-01-01T00:00:00Z',
          storage_address: 'other-address',
          signed_url: 'other-url',
          created_at: '2023-01-01T00:00:00Z',
          updated_at: '2023-01-01T00:00:00Z',
          tags: ['other'],
          images: []
        }
      };

      const result = getOtherBlueprintTags(complexSelections, 'base|level1|level2', mockBlueprint);

      // Should include:
      // - Parent tags: ['level1'] (from base|level1)
      // - All sibling tags: ['base'] (from base), ['level1'] (from base|level1), ['level2'] (from base|level1|level2), ['level3'] (from base|level1|level2|level3), ['other'] (from base|other)
      const expectedTags = new Set(['level1', 'base', 'level1', 'level2', 'level3', 'other']);
      expect(result).toEqual(expectedTags);
    });
  });
});
