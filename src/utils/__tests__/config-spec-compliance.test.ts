import { processConfigValues } from '../config-processing';
import type { ConfigTags } from '@/types';

describe('Config Spec Compliance Tests', () => {
  describe('Backend Constraint Computation', () => {
    it('should compute final require constraints for backend API', () => {
      const configValues: ConfigTags = {
        require: [
          { tag: 'shape|base' },
          { tag: 'size|width|2' }
        ]
      };

      const result = processConfigValues(configValues);
      // These are the final require constraints to send to backend API
      expect(result.require).toEqual(['shape|base', 'size|width|2']);
    });

    it('should compute final deny constraints for backend API', () => {
      const configValues: ConfigTags = {
        deny: [
          { tag: 'shape|wall' },
          { tag: 'build|s2w' }
        ]
      };

      const result = processConfigValues(configValues);
      // These are the final deny constraints to send to backend API
      expect(result.deny).toEqual(['shape|wall', 'build|s2w']);
    });

    it('should combine direct constraints with inherited constraints', () => {
      const configValues: ConfigTags = {
        require: [
          { tag: 'shape|base' }
        ],
        constrain: [
          { tag: 'texture' }
        ]
      };

      const parentTags = ['texture|dungeon_stone'];
      const result = processConfigValues(configValues, parentTags, []);

      // Final require array includes both direct and inherited constraints
      expect(result.require).toEqual(['shape|base', 'texture|dungeon_stone']);
    });
  });

  describe('Require Constraints', () => {
    it('should enforce exact tag matching', () => {
      const configValues: ConfigTags = {
        require: [
          { tag: 'shape|base' },
          { tag: 'size|width|2' }
        ]
      };

      const result = processConfigValues(configValues);
      expect(result.require).toEqual(['shape|base', 'size|width|2']);
    });

    it('should create AND relationship for multiple require entries', () => {
      const configValues: ConfigTags = {
        require: [
          { tag: 'shape|wall' },
          { tag: 'build|s2w' },
          { tag: 'connection|openforge' }
        ]
      };

      const result = processConfigValues(configValues);
      expect(result.require).toEqual(['shape|wall', 'build|s2w', 'connection|openforge']);
    });
  });

  describe('Deny Constraints', () => {
    it('should enforce exclusion matching', () => {
      const configValues: ConfigTags = {
        deny: [
          { tag: 'shape|wall' },
          { tag: 'build|s2w' }
        ]
      };

      const result = processConfigValues(configValues);
      expect(result.deny).toEqual(['shape|wall', 'build|s2w']);
    });

    it('should create OR relationship for multiple deny entries', () => {
      const configValues: ConfigTags = {
        deny: [
          { tag: 'shape|column|low' },
          { tag: 'shape|option|notch' }
        ]
      };

      const result = processConfigValues(configValues);
      expect(result.deny).toEqual(['shape|column|low', 'shape|option|notch']);
    });
  });

  describe('Accept Constraints', () => {
    it('should support hierarchical tag matching', () => {
      const configValues: ConfigTags = {
        accept: [
          { tag: 'shape|wall' }
        ]
      };

      // Note: Accept constraints are not processed by processConfigValues
      // They are handled at the UI/selection level
      const result = processConfigValues(configValues);
      expect(result.require).toEqual([]);
    });
  });

  describe('Constrain System - Parent Inheritance', () => {
    it('should inherit from parent tags when parent is enabled (default)', () => {
      const configValues: ConfigTags = {
        constrain: [
          { tag: 'texture' }
        ]
      };

      const parentTags = ['texture|dungeon_stone', 'connection|openforge'];
      const result = processConfigValues(configValues, parentTags, []);

      // Inherited tags become require constraints for backend
      expect(result.require).toEqual(['texture|dungeon_stone']);
    });

    it('should not inherit from parent when parent is disabled', () => {
      const configValues: ConfigTags = {
        constrain: [
          { tag: 'texture', parent: false }
        ]
      };

      const parentTags = ['texture|dungeon_stone', 'connection|openforge'];
      const result = processConfigValues(configValues, parentTags, []);

      expect(result.require).toEqual([]);
    });

    it('should inherit from parent by default when parent is not specified', () => {
      const configValues: ConfigTags = {
        constrain: [
          { tag: 'connection' }
        ]
      };

      const parentTags = ['connection|openforge', 'texture|stone'];
      const result = processConfigValues(configValues, parentTags, []);

      expect(result.require).toEqual(['connection|openforge']);
    });
  });

  describe('Constrain System - Sibling Inheritance', () => {
    it('should inherit from all siblings when siblings is undefined (default)', () => {
      const configValues: ConfigTags = {
        constrain: [
          { tag: 'texture' }
        ]
      };

      const siblingSelections = [
        { partName: 'wall', tags: ['texture|dungeon_stone'] },
        { partName: 'floor', tags: ['texture|wood'] }
      ];

      const result = processConfigValues(configValues, [], siblingSelections);

      // Inherited tags become require constraints for backend
      expect(result.require).toEqual(['texture|dungeon_stone', 'texture|wood']);
    });

    it('should inherit from specific siblings when siblings array is provided', () => {
      const configValues: ConfigTags = {
        constrain: [
          { tag: 'texture', siblings: ['wall'] }
        ]
      };

      const siblingSelections = [
        { partName: 'wall', tags: ['texture|dungeon_stone'] },
        { partName: 'floor', tags: ['texture|wood'] }
      ];

      const result = processConfigValues(configValues, [], siblingSelections);

      expect(result.require).toEqual(['texture|dungeon_stone']);
    });

    it('should not inherit from siblings when siblings array is empty', () => {
      const configValues: ConfigTags = {
        constrain: [
          { tag: 'texture', siblings: [] }
        ]
      };

      const siblingSelections = [
        { partName: 'wall', tags: ['texture|dungeon_stone'] },
        { partName: 'floor', tags: ['texture|wood'] }
      ];

      const result = processConfigValues(configValues, [], siblingSelections);

      expect(result.require).toEqual([]);
    });

    it('should handle invalid sibling names gracefully', () => {
      const configValues: ConfigTags = {
        constrain: [
          { tag: 'texture', siblings: ['nonexistent'] }
        ]
      };

      const siblingSelections = [
        { partName: 'wall', tags: ['texture|dungeon_stone'] }
      ];

      const result = processConfigValues(configValues, [], siblingSelections);

      expect(result.require).toEqual([]);
    });
  });

  describe('Constrain System - Combined Inheritance', () => {
    it('should combine parent and sibling inheritance', () => {
      const configValues: ConfigTags = {
        constrain: [
          { tag: 'texture' }
        ]
      };

      const parentTags = ['texture|dungeon_stone'];
      const siblingSelections = [
        { partName: 'wall', tags: ['texture|wood'] }
      ];

      const result = processConfigValues(configValues, parentTags, siblingSelections);

      // All inherited tags become require constraints for backend
      expect(result.require).toEqual(['texture|dungeon_stone', 'texture|wood']);
    });

    it('should combine parent and specific sibling inheritance', () => {
      const configValues: ConfigTags = {
        constrain: [
          { tag: 'texture', siblings: ['wall'] }
        ]
      };

      const parentTags = ['texture|dungeon_stone'];
      const siblingSelections = [
        { partName: 'wall', tags: ['texture|wood'] },
        { partName: 'floor', tags: ['texture|stone'] }
      ];

      const result = processConfigValues(configValues, parentTags, siblingSelections);

      expect(result.require).toEqual(['texture|dungeon_stone', 'texture|wood']);
    });

    it('should exclude parent when parent is false and use specific siblings', () => {
      const configValues: ConfigTags = {
        constrain: [
          { tag: 'texture', parent: false, siblings: ['wall'] }
        ]
      };

      const parentTags = ['texture|dungeon_stone'];
      const siblingSelections = [
        { partName: 'wall', tags: ['texture|wood'] },
        { partName: 'floor', tags: ['texture|stone'] }
      ];

      const result = processConfigValues(configValues, parentTags, siblingSelections);

      expect(result.require).toEqual(['texture|wood']);
    });
  });

  describe('Filter Mechanism', () => {
    it('should remove filtered tag prefixes from inherited tags', () => {
      const configValues: ConfigTags = {
        constrain: [
          { tag: 'connection' },
          { filter: 'connection|side' }
        ]
      };

      const siblingSelections = [
        { partName: 'wall', tags: ['connection|openforge', 'connection|side|female'] }
      ];

      const result = processConfigValues(configValues, [], siblingSelections);

      // Only non-filtered tags become require constraints for backend
      expect(result.require).toEqual(['connection|openforge']);
    });

    it('should handle multiple filters', () => {
      const configValues: ConfigTags = {
        constrain: [
          { tag: 'connection' },
          { filter: 'connection|side' },
          { filter: 'connection|openforge' }
        ]
      };

      const siblingSelections = [
        { partName: 'wall', tags: ['connection|openforge', 'connection|side|female', 'connection|other'] }
      ];

      const result = processConfigValues(configValues, [], siblingSelections);

      expect(result.require).toEqual(['connection|other']);
    });

    it('should apply filters after inheritance', () => {
      const configValues: ConfigTags = {
        constrain: [
          { tag: 'connection' },
          { filter: 'connection|side' }
        ]
      };

      const parentTags = ['connection|openforge'];
      const siblingSelections = [
        { partName: 'wall', tags: ['connection|side|female'] }
      ];

      const result = processConfigValues(configValues, parentTags, siblingSelections);

      expect(result.require).toEqual(['connection|openforge']);
    });
  });

  describe('Tag Specificity Filtering', () => {
    it('should filter out more specific tags while keeping same-level tags', () => {
      const configValues: ConfigTags = {
        constrain: [
          { tag: 'texture' }
        ]
      };

      const siblingSelections = [
        { partName: 'wall', tags: [
          'texture|wood',
          'texture|dungeon_stone',
          'texture|dungeon_stone|block',
          'texture|cave|detailed',
          'texture|cave'
        ]}
      ];

      const result = processConfigValues(configValues, [], siblingSelections);

      // Most general tags become require constraints for backend
      expect(result.require).toEqual(['texture|wood', 'texture|dungeon_stone', 'texture|cave']);
    });

    it('should handle multiple levels of tag specificity', () => {
      const configValues: ConfigTags = {
        constrain: [
          { tag: 'texture' }
        ]
      };

      const siblingSelections = [
        { partName: 'wall', tags: [
          'texture|stone',
          'texture|stone|rough',
          'texture|stone|rough|cracked',
          'texture|wood',
          'texture|wood|oak|stained'
        ]}
      ];

      const result = processConfigValues(configValues, [], siblingSelections);

      expect(result.require).toEqual(['texture|stone', 'texture|wood']);
    });
  });

  describe('Real-world Blueprint Examples', () => {
    it('should handle S2W corner blueprint column constraints', () => {
      const configValues: ConfigTags = {
        require: [
          { tag: 'shape|column|corner' },
          { tag: 'build|s2w' },
          { tag: 'size|column_shape|L' }
        ],
        deny: [
          { tag: 'shape|column|low' }
        ],
        constrain: [
          { tag: 'connection|side' }
        ]
      };

      const result = processConfigValues(configValues);
      // Direct require/deny constraints are passed through to backend
      expect(result.require).toEqual(['shape|column|corner', 'build|s2w', 'size|column_shape|L']);
      expect(result.deny).toEqual(['shape|column|low']);
    });

    it('should handle S2W corner blueprint right wall with fulfillment', () => {
      const configValues: ConfigTags = {
        require: [
          { tag: 'build|s2w' },
          { tag: 'shape|corner|right' },
          { tag: 'connection|openforge' },
          { tag: 'size|width|2' }
        ],
        deny: [
          { tag: 'shape|column|low' }
        ],
        constrain: [
          { tag: 'connection|side' }
        ]
      };

      const result = processConfigValues(configValues);
      expect(result.require).toEqual(['build|s2w', 'shape|corner|right', 'connection|openforge', 'size|width|2']);
      expect(result.deny).toEqual(['shape|column|low']);
    });

    it('should handle S2W corner blueprint base with connection filtering', () => {
      const configValues: ConfigTags = {
        require: [
          { tag: 'shape|base' },
          { tag: 'shape|base|square' },
          { tag: 'size|width|2' },
          { tag: 'size|depth|2' }
        ],
        deny: [
          { tag: 'shape|wall' },
          { tag: 'build|s2w' },
          { tag: 'shape|option|notch' }
        ],
        constrain: [
          { tag: 'connection' },
          { filter: 'connection|side' }
        ]
      };

      const siblingSelections = [
        { partName: 'right wall', tags: ['connection|openforge', 'connection|side|female'] },
        { partName: 'left wall', tags: ['connection|openforge', 'connection|side|male'] }
      ];

      const result = processConfigValues(configValues, [], siblingSelections);

      // Final require array includes both direct and inherited constraints
      expect(result.require).toEqual([
        'shape|base', 'shape|base|square', 'size|width|2', 'size|depth|2',
        'connection|openforge'
      ]);
      expect(result.deny).toEqual(['shape|wall', 'build|s2w', 'shape|option|notch']);
    });
  });

  describe('Constraint Conflict Handling', () => {
    it('should handle conflicting constraints from multiple siblings', () => {
      const configValues: ConfigTags = {
        constrain: [
          { tag: 'texture' }
        ]
      };

      const siblingSelections = [
        { partName: 'wall', tags: ['texture|stone'] },
        { partName: 'floor', tags: ['texture|wood'] }
      ];

      const result = processConfigValues(configValues, [], siblingSelections);

      // Both constraints are sent to backend - backend will handle the conflict
      expect(result.require).toEqual(['texture|stone', 'texture|wood']);
    });

    it('should handle conflicting constraints with filters', () => {
      const configValues: ConfigTags = {
        constrain: [
          { tag: 'connection' },
          { filter: 'connection|side' }
        ]
      };

      const siblingSelections = [
        { partName: 'wall', tags: ['connection|openforge', 'connection|side|female'] },
        { partName: 'floor', tags: ['connection|openforge', 'connection|side|male'] }
      ];

      const result = processConfigValues(configValues, [], siblingSelections);

      // Only non-filtered connections are sent to backend
      expect(result.require).toEqual(['connection|openforge']);
    });
  });

  describe('Edge Cases', () => {
    it('should handle empty config values', () => {
      const result = processConfigValues(null);
      expect(result).toEqual({ require: [], deny: [] });
    });

    it('should handle config with no tags section', () => {
      const configValues: ConfigTags = {};
      const result = processConfigValues(configValues);
      expect(result).toEqual({ require: [], deny: [] });
    });

    it('should handle empty arrays in all constraint types', () => {
      const configValues: ConfigTags = {
        require: [],
        deny: [],
        accept: [],
        constrain: []
      };

      const result = processConfigValues(configValues);
      expect(result).toEqual({ require: [], deny: [] });
    });

    it('should handle constrain with only filter entries', () => {
      const configValues: ConfigTags = {
        constrain: [
          { filter: 'connection|side' },
          { filter: 'connection|openforge' }
        ]
      };

      const result = processConfigValues(configValues);
      expect(result).toEqual({ require: [], deny: [] });
    });

    it('should handle constrain with mixed tag and filter entries', () => {
      const configValues: ConfigTags = {
        constrain: [
          { tag: 'texture' },
          { filter: 'texture|stone' }
        ]
      };

      const siblingSelections = [
        { partName: 'wall', tags: ['texture|stone', 'texture|wood'] }
      ];

      const result = processConfigValues(configValues, [], siblingSelections);
      expect(result.require).toEqual(['texture|wood']);
    });
  });

  describe('API Integration', () => {
    it('should produce backend-compatible constraint arrays', () => {
      const configValues: ConfigTags = {
        require: [
          { tag: 'shape|base' }
        ],
        deny: [
          { tag: 'build|s2w' }
        ],
        constrain: [
          { tag: 'texture' }
        ]
      };

      const parentTags = ['texture|dungeon_stone'];
      const result = processConfigValues(configValues, parentTags, []);

      // These arrays are ready to send to backend API
      expect(result.require).toEqual(['shape|base', 'texture|dungeon_stone']);
      expect(result.deny).toEqual(['build|s2w']);
    });

    it('should handle complex inheritance scenarios for backend', () => {
      const configValues: ConfigTags = {
        require: [
          { tag: 'shape|wall' }
        ],
        constrain: [
          { tag: 'connection', siblings: ['floor'] },
          { tag: 'texture', parent: false }
        ]
      };

      const parentTags = ['texture|stone', 'connection|openforge'];
      const siblingSelections = [
        { partName: 'floor', tags: ['connection|side|female'] },
        { partName: 'ceiling', tags: ['connection|top'] }
      ];

      const result = processConfigValues(configValues, parentTags, siblingSelections);

      // Final arrays for backend API
      // connection inherits from parent AND floor sibling (siblings only restricts which siblings, not parent)
      // texture does not inherit from parent (parent: false)
      expect(result.require).toEqual(['shape|wall', 'connection|openforge', 'connection|side|female']);
      expect(result.deny).toEqual([]);
    });
  });
});
