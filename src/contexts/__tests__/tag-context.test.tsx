import React from 'react';
import { render, screen, act, waitFor } from '@testing-library/react';
import { TagProvider, useTagContext } from '../tag-context';
import { createStore } from 'zustand';
import type { TagStore } from '@/stores/tag-store';

// Mock fetch for async methods
const fetchMock = jest.fn();
global.fetch = fetchMock;

// Create a mock store that can actually update state
const createMockTagStore = () => {
  return createStore((set) => ({
    data: {},
    expandedNodes: {},
    selectedTags: [],
    denyTags: [],
    blueprints: [],
    paging: null,
    autoload: false,
    search_models: false,
    search_blueprints: false,
    searchTerm: null,
    tagDescriptions: {},
    fetchData: jest.fn(),
    setData: jest.fn(),
    toggleNode: (key: string) => {
      set((state: TagStore) => ({
        expandedNodes: {
          ...state.expandedNodes,
          [key]: !state.expandedNodes[key],
        },
      }));
    },
    addTag: (tag: string) => {
      set((state: TagStore) => {
        if (!state.selectedTags.includes(tag)) {
          return { selectedTags: [...state.selectedTags, tag] };
        }
        return state;
      });
    },
    addAllTags: (tags: string[]) => {
      set((state: TagStore) => {
        const uniqueTags = Array.from(new Set([...state.selectedTags, ...tags]));
        return { selectedTags: uniqueTags };
      });
    },
    removeTag: (tag: string) => {
      set((state: TagStore) => ({
        selectedTags: state.selectedTags.filter((t: string) => t !== tag),
      }));
    },
    clearTags: () => {
      set({ selectedTags: [], denyTags: [], searchTerm: null });
    },
    addDenyTag: (tag: string) => {
      set((state: TagStore) => {
        if (!state.denyTags.includes(tag)) {
          return { denyTags: [...state.denyTags, tag] };
        }
        return state;
      });
    },
    removeDenyTag: (tag: string) => {
      set((state: TagStore) => ({
        denyTags: state.denyTags.filter((t: string) => t !== tag),
      }));
    },
    setTagState: (tags: { require?: string[]; deny?: string[] }) => {
      set({
        selectedTags: tags.require || [],
        denyTags: tags.deny || [],
      });
    },
    setSearchTerm: (term: string | null) => {
      set({ searchTerm: term });
    },
    fetchBlueprints: async () => {
      fetchMock();
      set({
        blueprints: [{ id: '1', blueprint_name: 'Test Blueprint' }],
        paging: { total_count: 1 }
      });
    },
    setBlueprints: (blueprints: unknown[], paging: unknown) => {
      set({ blueprints, paging });
    },
    fetchTagDescriptions: async () => {
      fetchMock();
      set({ tagDescriptions: { test: 'description' } });
    },
  }));
};

// Mock the store creation
jest.mock('../../stores/tag-store', () => ({
  createTagStore: jest.fn(() => createMockTagStore()),
}));

const TestComponent = () => {
  const selectedTags = useTagContext((state) => state.selectedTags);
  const denyTags = useTagContext((state) => state.denyTags);
  const tagDescriptions = useTagContext((state) => state.tagDescriptions);
  const data = useTagContext((state) => state.data);
  const expandedNodes = useTagContext((state) => state.expandedNodes);
  const searchTerm = useTagContext((state) => state.searchTerm);
  const blueprints = useTagContext((state) => state.blueprints);
  const paging = useTagContext((state) => state.paging);
  const autoload = useTagContext((state) => state.autoload);
  const addTag = useTagContext((state) => state.addTag);
  const removeTag = useTagContext((state) => state.removeTag);
  const clearTags = useTagContext((state) => state.clearTags);
  const addAllTags = useTagContext((state) => state.addAllTags);
  const setTagState = useTagContext((state) => state.setTagState);
  const setSearchTerm = useTagContext((state) => state.setSearchTerm);
  const toggleNode = useTagContext((state) => state.toggleNode);
  const fetchBlueprints = useTagContext((state) => state.fetchBlueprints);
  const fetchTagDescriptions = useTagContext((state) => state.fetchTagDescriptions);

  return (
    <div>
      <div data-testid="selected-tags">{selectedTags.join(',')}</div>
      <div data-testid="deny-tags">{denyTags.join(',')}</div>
      <div data-testid="search-term">{searchTerm || ''}</div>
      <div data-testid="autoload">{String(autoload)}</div>
      <div data-testid="blueprints-count">{blueprints.length}</div>
      <div data-testid="paging-total">{paging?.total_count ?? ''}</div>
      <div data-testid="tag-descriptions">{Object.keys(tagDescriptions).length}</div>
      <div data-testid="data-root-keys">{Object.keys(data).join(',')}</div>
      <div data-testid="expanded-nodes">{Object.keys(expandedNodes).join(',')}</div>
      <button data-testid="add-tag" onClick={() => addTag('foo|bar')}>Add Tag</button>
      <button data-testid="remove-tag" onClick={() => removeTag('foo|bar')}>Remove Tag</button>
      <button data-testid="clear-tags" onClick={() => clearTags()}>Clear Tags</button>
      <button data-testid="add-all-tags" onClick={() => addAllTags(['a|b','c|d'])}>Add All Tags</button>
      <button data-testid="set-tag-state" onClick={() => setTagState({ require: ['x'], deny: ['y'] })}>Set Tag State</button>
      <button data-testid="set-search-term" onClick={() => setSearchTerm('searchme')}>Set Search Term</button>
      <button data-testid="toggle-node" onClick={() => toggleNode('root')}>Toggle Node</button>
      <button data-testid="fetch-blueprints" onClick={() => fetchBlueprints()}>Fetch Blueprints</button>
      <button data-testid="fetch-tag-descriptions" onClick={() => fetchTagDescriptions()}>Fetch Tag Descriptions</button>
    </div>
  );
};

describe('TagContext', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    fetchMock.mockReset();
    fetchMock.mockResolvedValue({
      ok: true,
      json: async () => ({
        paging: { total_count: 1, start_count: 0 },
        blueprints: [{ id: 'b1', blueprint_name: 'BP1', tags: [] }],
        tag_counts: [],
      }),
      text: async () => JSON.stringify({ foo: 'desc' }),
    });
  });

  it('provides default state and allows tag manipulation', async () => {
    await act(async () => {
      render(
        <TagProvider autoload={false}>
          <TestComponent />
        </TagProvider>
      );
    });

    // Wait for any initial async operations to complete
    await waitFor(() => {
      expect(screen.getByTestId('selected-tags')).toBeInTheDocument();
    });

    // Default state
    expect(screen.getByTestId('selected-tags')).toHaveTextContent('');
    expect(screen.getByTestId('deny-tags')).toHaveTextContent('');
    expect(screen.getByTestId('search-term')).toHaveTextContent('');
    expect(screen.getByTestId('autoload')).toHaveTextContent('false');
    expect(screen.getByTestId('blueprints-count')).toHaveTextContent('0');
    expect(screen.getByTestId('paging-total')).toHaveTextContent('');
    expect(screen.getByTestId('tag-descriptions')).toHaveTextContent('0');

    // Add tag
    act(() => {
      screen.getByTestId('add-tag').click();
    });
    expect(screen.getByTestId('selected-tags')).toHaveTextContent('foo|bar');

    // Remove tag
    act(() => {
      screen.getByTestId('remove-tag').click();
    });
    expect(screen.getByTestId('selected-tags')).toHaveTextContent('');

    // Add all tags
    act(() => {
      screen.getByTestId('add-all-tags').click();
    });
    expect(screen.getByTestId('selected-tags')).toHaveTextContent('a|b,c|d');

    // Clear tags
    act(() => {
      screen.getByTestId('clear-tags').click();
    });
    expect(screen.getByTestId('selected-tags')).toHaveTextContent('');
  });

  it('setTagState sets require and deny tags', async () => {
    await act(async () => {
      render(
        <TagProvider autoload={false}>
          <TestComponent />
        </TagProvider>
      );
    });

    await waitFor(() => {
      expect(screen.getByTestId('selected-tags')).toBeInTheDocument();
    });

    act(() => {
      screen.getByTestId('set-tag-state').click();
    });
    expect(screen.getByTestId('selected-tags')).toHaveTextContent('x');
    expect(screen.getByTestId('deny-tags')).toHaveTextContent('y');
  });

  it('setSearchTerm updates searchTerm', async () => {
    await act(async () => {
      render(
        <TagProvider autoload={false}>
          <TestComponent />
        </TagProvider>
      );
    });

    await waitFor(() => {
      expect(screen.getByTestId('selected-tags')).toBeInTheDocument();
    });

    act(() => {
      screen.getByTestId('set-search-term').click();
    });
    expect(screen.getByTestId('search-term')).toHaveTextContent('searchme');
  });

  it('toggleNode toggles expandedNodes', async () => {
    await act(async () => {
      render(
        <TagProvider autoload={false}>
          <TestComponent />
        </TagProvider>
      );
    });

    await waitFor(() => {
      expect(screen.getByTestId('selected-tags')).toBeInTheDocument();
    });

    expect(screen.getByTestId('expanded-nodes')).toHaveTextContent('');
    act(() => {
      screen.getByTestId('toggle-node').click();
    });
    expect(screen.getByTestId('expanded-nodes')).toHaveTextContent('root');
    act(() => {
      screen.getByTestId('toggle-node').click();
    });
    expect(screen.getByTestId('expanded-nodes')).toHaveTextContent('root');
  });

  it('fetchBlueprints fetches and updates blueprints and paging', async () => {
    await act(async () => {
      render(
        <TagProvider autoload={false}>
          <TestComponent />
        </TagProvider>
      );
    });

    await waitFor(() => {
      expect(screen.getByTestId('selected-tags')).toBeInTheDocument();
    });

    await act(async () => {
      screen.getByTestId('fetch-blueprints').click();
    });
    expect(fetchMock).toHaveBeenCalled();
    expect(screen.getByTestId('blueprints-count')).toHaveTextContent('1');
    expect(screen.getByTestId('paging-total')).toHaveTextContent('1');
  });

  it('fetchTagDescriptions fetches and updates tagDescriptions', async () => {
    await act(async () => {
      render(
        <TagProvider autoload={false}>
          <TestComponent />
        </TagProvider>
      );
    });

    await waitFor(() => {
      expect(screen.getByTestId('selected-tags')).toBeInTheDocument();
    });

    await act(async () => {
      screen.getByTestId('fetch-tag-descriptions').click();
    });
    expect(fetchMock).toHaveBeenCalled();
    expect(screen.getByTestId('tag-descriptions')).not.toHaveTextContent('0');
  });
});
