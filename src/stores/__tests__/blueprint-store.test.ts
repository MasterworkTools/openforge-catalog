import { createBlueprintStore } from '../blueprint-store';
import type { Blueprint } from '@/types';

// Mock fetch globally
global.fetch = jest.fn();

const mockBlueprint: Blueprint = {
  id: '123e4567-e89b-12d3-a456-426614174000',
  blueprint_name: 'Test Blueprint',
  blueprint_type: 'model',
  file_md5: 'd41d8cd98f00b204e9800998ecf8427e',
  file_size: 1024,
  file_name: 'test.stl',
  full_name: 'test/test.stl',
  file_modified_at: '2023-01-01T00:00:00Z',
  storage_address: 'test/address',
  signed_url: 'https://example.com/test.stl',
  created_at: '2023-01-01T00:00:00Z',
  updated_at: '2023-01-01T00:00:00Z',
  tags: ['test', 'model'],
  images: []
};

describe('BlueprintStore', () => {
  let store: ReturnType<typeof createBlueprintStore>;

  beforeEach(() => {
    store = createBlueprintStore();
    jest.clearAllMocks();
  });

  describe('setSelectedBlueprint', () => {
    it('should set selected blueprint', () => {
      store.getState().setSelectedBlueprint(mockBlueprint);
      expect(store.getState().selectedBlueprint).toBe(mockBlueprint);
    });

    it('should clear config selections when setting different blueprint', () => {
      // Set initial config selections
      store.getState().setConfigSelection('part1', mockBlueprint);
      expect(store.getState().configSelections).toHaveProperty('part1');

      // Set a different blueprint
      const differentBlueprint = { ...mockBlueprint, id: 'different-id' };
      store.getState().setSelectedBlueprint(differentBlueprint);

      expect(store.getState().selectedBlueprint).toBe(differentBlueprint);
      expect(store.getState().configSelections).toEqual({});
    });

    it('should clear config selections when setting same blueprint (current behavior)', () => {
      // Set initial config selections
      store.getState().setConfigSelection('part1', mockBlueprint);
      expect(store.getState().configSelections).toHaveProperty('part1');

      // Set the same blueprint reference - this actually clears config selections
      store.getState().setSelectedBlueprint(mockBlueprint);

      expect(store.getState().selectedBlueprint).toBe(mockBlueprint);
      // The current implementation clears config selections even for the same blueprint
      expect(store.getState().configSelections).toEqual({});
    });

    it('should set selected blueprint to null', () => {
      store.getState().setSelectedBlueprint(mockBlueprint);
      store.getState().setSelectedBlueprint(null);
      expect(store.getState().selectedBlueprint).toBeNull();
    });
  });

  describe('fetchBlueprintById', () => {
    it('should fetch blueprint by id successfully', async () => {
      (fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => mockBlueprint
      });

      const result = await store.getState().fetchBlueprintById('123e4567-e89b-12d3-a456-426614174000');

      expect(fetch).toHaveBeenCalledWith('/api/blueprints/123e4567-e89b-12d3-a456-426614174000');
      expect(result).toEqual(mockBlueprint);
    });

    it('should throw error when fetch fails', async () => {
      (fetch as jest.Mock).mockResolvedValueOnce({
        ok: false,
        status: 404
      });

      await expect(store.getState().fetchBlueprintById('invalid-id')).rejects.toThrow('Failed to fetch blueprint');
      expect(fetch).toHaveBeenCalledWith('/api/blueprints/invalid-id');
    });
  });

  describe('fetchBlueprintByMd5', () => {
    it('should fetch blueprint by md5 successfully', async () => {
      (fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => mockBlueprint
      });

      const result = await store.getState().fetchBlueprintByMd5('d41d8cd98f00b204e9800998ecf8427e');

      expect(fetch).toHaveBeenCalledWith('/api/blueprints/md5/d41d8cd98f00b204e9800998ecf8427e');
      expect(result).toEqual(mockBlueprint);
    });

    it('should throw error when fetch fails', async () => {
      (fetch as jest.Mock).mockResolvedValueOnce({
        ok: false,
        status: 404
      });

      await expect(store.getState().fetchBlueprintByMd5('invalid-md5')).rejects.toThrow('Failed to fetch blueprint');
      expect(fetch).toHaveBeenCalledWith('/api/blueprints/md5/invalid-md5');
    });
  });

  describe('setConfigSelection', () => {
    it('should add blueprint to config selections', () => {
      store.getState().setConfigSelection('part1', mockBlueprint);
      expect(store.getState().configSelections).toEqual({
        part1: mockBlueprint
      });
    });

    it('should update existing config selection', () => {
      const updatedBlueprint = { ...mockBlueprint, blueprint_name: 'Updated Blueprint' };

      store.getState().setConfigSelection('part1', mockBlueprint);
      store.getState().setConfigSelection('part1', updatedBlueprint);

      expect(store.getState().configSelections).toEqual({
        part1: updatedBlueprint
      });
    });

    it('should remove blueprint when setting to null', () => {
      store.getState().setConfigSelection('part1', mockBlueprint);
      store.getState().setConfigSelection('part1', null);

      expect(store.getState().configSelections).toEqual({});
    });

    it('should handle multiple config selections', () => {
      const blueprint2 = { ...mockBlueprint, id: 'different-id', blueprint_name: 'Blueprint 2' };

      store.getState().setConfigSelection('part1', mockBlueprint);
      store.getState().setConfigSelection('part2', blueprint2);

      expect(store.getState().configSelections).toEqual({
        part1: mockBlueprint,
        part2: blueprint2
      });
    });
  });

  describe('clearConfigSelections', () => {
    it('should clear all config selections', () => {
      store.getState().setConfigSelection('part1', mockBlueprint);
      store.getState().setConfigSelection('part2', mockBlueprint);

      expect(store.getState().configSelections).not.toEqual({});

      store.getState().clearConfigSelections();
      expect(store.getState().configSelections).toEqual({});
    });
  });
});
