import { createTagStore } from '../tag-store';
import type { Blueprint, Paging } from '@/types';

// Mock fetch globally
global.fetch = jest.fn();

// Use a persistent mock for setSelectedBlueprint
const setSelectedBlueprint = jest.fn();
const mockBlueprintStore = {
  getState: jest.fn(() => ({
    setSelectedBlueprint
  }))
};

Object.defineProperty(window, '__BLUEPRINT_STORE__', {
  value: mockBlueprintStore,
  writable: true
});

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

const mockPaging: Paging = {
  previous_token: undefined,
  next_token: 'next-page-token',
  total_count: 100,
  start_count: 0
};

describe('TagStore', () => {
  let store: ReturnType<typeof createTagStore>;

  beforeEach(() => {
    store = createTagStore();
    jest.clearAllMocks();
    (global.fetch as jest.Mock).mockImplementation(() =>
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ blueprints: [], paging: {}, tag_counts: {} }),
      })
    );
  });

  describe('setData', () => {
    it('should transform tag counts into hierarchical structure', () => {
      const tagCounts = {
        'tag1': 5,
        'tag1|tag2': 3,
        'tag1|tag4': 2,
        'tag1|tag2|tag3': 1,
      };

      store.getState().setData(tagCounts);

      const data = store.getState().data;
      expect(data.tag1).toBeDefined();
      expect(data.tag1.__count).toBe(5);
      expect(data.tag1.__totalCount).toBe(11); // 5 + 3 + 2 + 1
      expect(data.tag1.__subTags).toBe(2); // tag2 and tag4
      expect(data.tag1.children!.tag2.__count).toBe(3);
      expect(data.tag1.children!.tag2.__totalCount).toBe(4); // 3 + 1
      expect(data.tag1.children!.tag2.__subTags).toBe(1); // tag3
      expect(data.tag1.children!.tag2.children!.tag3.__count).toBe(1);
      expect(data.tag1.children!.tag4.__count).toBe(2);
    });

    it('should handle empty tag counts', () => {
      store.getState().setData({});
      expect(store.getState().data).toEqual({});
    });

    it('should handle single level tags', () => {
      const tagCounts = {
        'tag1': 5,
        'tag2': 3,
      };

      store.getState().setData(tagCounts);

      const data = store.getState().data;
      expect(data.tag1.__count).toBe(5);
      expect(data.tag1.__totalCount).toBe(5);
      expect(data.tag1.__subTags).toBe(0);
      expect(data.tag2.__count).toBe(3);
      expect(data.tag2.__totalCount).toBe(3);
      expect(data.tag2.__subTags).toBe(0);
    });
  });

  describe('toggleNode', () => {
    it('should toggle node expansion state', () => {
      const initialState = store.getState().expandedNodes;
      expect(initialState['test-key']).toBeUndefined();

      store.getState().toggleNode('test-key');
      expect(store.getState().expandedNodes['test-key']).toBe(true);

      store.getState().toggleNode('test-key');
      expect(store.getState().expandedNodes['test-key']).toBe(false);
    });

    it('should handle multiple nodes independently', () => {
      store.getState().toggleNode('key1');
      store.getState().toggleNode('key2');

      expect(store.getState().expandedNodes['key1']).toBe(true);
      expect(store.getState().expandedNodes['key2']).toBe(true);
    });
  });

  describe('addTag', () => {
    it('should add tag to selected tags', () => {
      store.getState().addTag('test-tag');
      expect(store.getState().selectedTags).toContain('test-tag');
    });

    it('should not add duplicate tags', () => {
      store.getState().addTag('test-tag');
      store.getState().addTag('test-tag');

      const selectedTags = store.getState().selectedTags;
      expect(selectedTags.filter(tag => tag === 'test-tag')).toHaveLength(1);
    });

    it('should call fetchBlueprints after adding tag', async () => {
      (fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ blueprints: [], paging: mockPaging, tag_counts: {} })
      });

      store.getState().addTag('test-tag');

      // Wait for the async fetchBlueprints call
      await new Promise(resolve => setTimeout(resolve, 0));

      expect(fetch).toHaveBeenCalled();
    });

    it('should remove tag from denyTags when adding to selectedTags', () => {
      store.getState().addDenyTag('conflict-tag');
      expect(store.getState().denyTags).toContain('conflict-tag');

      store.getState().addTag('conflict-tag');
      expect(store.getState().denyTags).not.toContain('conflict-tag');
      expect(store.getState().selectedTags).toContain('conflict-tag');
    });
  });

  describe('addAllTags', () => {
    it('should add multiple tags without duplicates', () => {
      store.getState().addTag('existing-tag');
      store.getState().addAllTags(['new-tag1', 'new-tag2', 'existing-tag']);

      const selectedTags = store.getState().selectedTags;
      expect(selectedTags).toContain('existing-tag');
      expect(selectedTags).toContain('new-tag1');
      expect(selectedTags).toContain('new-tag2');
      expect(selectedTags.filter(tag => tag === 'existing-tag')).toHaveLength(1);
    });

    it('should call fetchBlueprints after adding tags', async () => {
      (fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ blueprints: [], paging: mockPaging, tag_counts: {} })
      });

      store.getState().addAllTags(['tag1', 'tag2']);

      await new Promise(resolve => setTimeout(resolve, 0));
      expect(fetch).toHaveBeenCalled();
    });
  });

  describe('removeTag', () => {
    it('should remove tag from selected tags', () => {
      store.getState().addTag('test-tag');
      store.getState().removeTag('test-tag');
      expect(store.getState().selectedTags).not.toContain('test-tag');
    });

    it('should call fetchBlueprints after removing tag', async () => {
      (fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ blueprints: [], paging: mockPaging, tag_counts: {} })
      });

      store.getState().addTag('test-tag');
      store.getState().removeTag('test-tag');

      await new Promise(resolve => setTimeout(resolve, 0));
      expect(fetch).toHaveBeenCalled();
    });

    it('should remove tag from both selectedTags and denyTags', () => {
      store.getState().addTag('selected-tag');
      store.getState().addDenyTag('deny-tag');

      store.getState().removeTag('selected-tag');
      expect(store.getState().selectedTags).not.toContain('selected-tag');

      store.getState().removeTag('deny-tag');
      expect(store.getState().denyTags).not.toContain('deny-tag');
    });
  });

  describe('addDenyTag', () => {
    it('should add tag to deny tags', () => {
      store.getState().addDenyTag('deny-tag');
      expect(store.getState().denyTags).toContain('deny-tag');
    });

    it('should not add duplicate deny tags', () => {
      store.getState().addDenyTag('deny-tag');
      store.getState().addDenyTag('deny-tag');

      const denyTags = store.getState().denyTags;
      expect(denyTags.filter(tag => tag === 'deny-tag')).toHaveLength(1);
    });

    it('should remove tag from selectedTags when adding to denyTags', () => {
      store.getState().addTag('conflict-tag');
      expect(store.getState().selectedTags).toContain('conflict-tag');

      store.getState().addDenyTag('conflict-tag');
      expect(store.getState().selectedTags).not.toContain('conflict-tag');
      expect(store.getState().denyTags).toContain('conflict-tag');
    });
  });

  describe('removeDenyTag', () => {
    it('should remove tag from deny tags', () => {
      store.getState().addDenyTag('deny-tag');
      store.getState().removeDenyTag('deny-tag');
      expect(store.getState().denyTags).not.toContain('deny-tag');
    });
  });

  describe('clearTags', () => {
    it('should clear all selected and deny tags', () => {
      store.getState().addTag('selected-tag');
      store.getState().addDenyTag('deny-tag');
      store.getState().setSearchTerm('search-term');

      store.getState().clearTags();

      expect(store.getState().selectedTags).toEqual([]);
      expect(store.getState().denyTags).toEqual([]);
      expect(store.getState().searchTerm).toBeNull();
    });

    it('should clear blueprint selection if blueprint store exists', () => {
      store.getState().clearTags();
      // Check that setSelectedBlueprint(null) was called at least once
      const setSelectedBlueprint = mockBlueprintStore.getState().setSelectedBlueprint;
      expect(setSelectedBlueprint).toHaveBeenCalledWith(null);
    });
  });

  describe('setTagState', () => {
    it('should set require and deny tags', () => {
      store.getState().setTagState({
        require: ['tag1', 'tag2'],
        deny: ['deny1']
      });

      expect(store.getState().selectedTags).toEqual(['tag1', 'tag2']);
      expect(store.getState().denyTags).toEqual(['deny1']);
    });

    it('should handle partial tag state', () => {
      store.getState().setTagState({
        require: ['tag1']
      });

      expect(store.getState().selectedTags).toEqual(['tag1']);
      expect(store.getState().denyTags).toEqual([]);
    });
  });

  describe('setSearchTerm', () => {
    it('should set search term', () => {
      store.getState().setSearchTerm('test-search');
      expect(store.getState().searchTerm).toBe('test-search');
    });

    it('should clear search term when set to null', () => {
      store.getState().setSearchTerm('test-search');
      store.getState().setSearchTerm(null);
      expect(store.getState().searchTerm).toBeNull();
    });
  });

  describe('fetchData', () => {
    it('should fetch tag data successfully', async () => {
      const mockTagCounts = { 'tag1': 5, 'tag2': 3 };
      (fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ tag_counts: mockTagCounts })
      });

      await store.getState().fetchData();

      expect(fetch).toHaveBeenCalledWith('/api/blueprints/tags?models=false&blueprints=false', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          require: [],
          deny: []
        })
      });
      expect(store.getState().data.tag1.__count).toBe(5);
      expect(store.getState().data.tag2.__count).toBe(3);
    });

    it('should include search parameters when not defaults', async () => {
      store = createTagStore(false, false, true); // search_blueprints = true
      (fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ tag_counts: {} })
      });

      await store.getState().fetchData();

      expect(fetch).toHaveBeenCalledWith('/api/blueprints/tags?models=false&blueprints=true', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          require: [],
          deny: []
        })
      });
    });

    it('should include selected and deny tags in request body', async () => {
      store.getState().addTag('selected-tag');
      store.getState().addDenyTag('deny-tag');

      const mockTagCounts = { 'tag1': 5 };
      (fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ tag_counts: mockTagCounts })
      });

      await store.getState().fetchData();

      expect(fetch).toHaveBeenCalledWith('/api/blueprints/tags?models=false&blueprints=false', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          require: [{ tag: 'selected-tag' }],
          deny: [{ tag: 'deny-tag' }]
        })
      });
    });
  });

  describe('fetchBlueprints', () => {
    it('should fetch blueprints with selected and deny tags', async () => {
      store.getState().addTag('selected-tag');
      store.getState().addDenyTag('deny-tag');

      (fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          blueprints: [mockBlueprint],
          paging: mockPaging,
          tag_counts: {}
        })
      });

      await store.getState().fetchBlueprints();

      expect(fetch).toHaveBeenCalledWith('/api/blueprints/tags?models=false&blueprints=false', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          require: [{ tag: 'selected-tag' }],
          deny: [{ tag: 'deny-tag' }]
        })
      });
    });

    it('should include search term in URL params', async () => {
      store.getState().setSearchTerm('test-search');

      (fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          blueprints: [],
          paging: mockPaging,
          tag_counts: {}
        })
      });

      await store.getState().fetchBlueprints();

      expect(fetch).toHaveBeenCalledWith('/api/blueprints/tags?models=false&blueprints=false&search=test-search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          require: [],
          deny: []
        })
      });
    });

    it('should include pagination parameters', async () => {
      (fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          blueprints: [],
          paging: mockPaging,
          tag_counts: {}
        })
      });

      await store.getState().fetchBlueprints({ next: 'next-token' });

      expect(fetch).toHaveBeenCalledWith('/api/blueprints/tags?models=false&blueprints=false&next=next-token', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          require: [],
          deny: []
        })
      });
    });
  });

  describe('setBlueprints', () => {
    it('should set blueprints and paging', () => {
      const blueprints = [mockBlueprint];
      const paging = mockPaging;

      store.getState().setBlueprints(blueprints, paging);

      expect(store.getState().blueprints).toEqual(blueprints);
      expect(store.getState().paging).toEqual(paging);
    });
  });

  describe('fetchTagDescriptions', () => {
    it('should fetch tag descriptions successfully', async () => {
      const mockDescriptions = {
        'tag1': 'Description for tag1',
        'tag2': 'Description for tag2'
      };

      (fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => mockDescriptions
      });

      await store.getState().fetchTagDescriptions();

      expect(fetch).toHaveBeenCalledWith('/api/tag-descriptions');
      expect(store.getState().tagDescriptions).toEqual(mockDescriptions);
    });
  });

  describe('store initialization', () => {
    it('should initialize with default values', () => {
      const state = store.getState();
      expect(state.data).toEqual({});
      expect(state.expandedNodes).toEqual({});
      expect(state.selectedTags).toEqual([]);
      expect(state.denyTags).toEqual([]);
      expect(state.blueprints).toEqual([]);
      expect(state.paging).toBeNull();
      expect(state.autoload).toBe(false);
      expect(state.search_models).toBe(false);
      expect(state.search_blueprints).toBe(false);
      expect(state.searchTerm).toBeNull();
      expect(state.tagDescriptions).toEqual({});
    });

    it('should initialize with custom parameters', () => {
      store = createTagStore(true, true, true);
      const state = store.getState();
      expect(state.autoload).toBe(true);
      expect(state.search_models).toBe(true);
      expect(state.search_blueprints).toBe(true);
    });
  });
});
