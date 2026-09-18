import React from 'react';
import { render, screen, fireEvent, act } from '@testing-library/react';
import { InstructionsPartSearch } from '../instructions-part-search';
import { useTagContext } from '@/contexts/tag-context';
import type { TagStore } from '@/stores/tag-store';

jest.mock('@/contexts/tag-context', () => ({
  useTagContext: jest.fn(),
}));

describe('InstructionsPartSearch', () => {
  const mockAddTag = jest.fn();
  const mockRemoveTag = jest.fn();
  const mockSelectedTags: string[] = [];
  const mockTagDescriptions = {
    'build': 'Build description',
    'build|separate wall': 'Separate wall desc',
    'component|door|arched': 'Arched door desc',
    'texture|dungeon_stone': 'Dungeon stone desc',
  };

  beforeEach(() => {
    (useTagContext as jest.Mock).mockImplementation((selector: (state: TagStore) => unknown) =>
      selector({
        addTag: mockAddTag,
        removeTag: mockRemoveTag,
        selectedTags: mockSelectedTags,
        tagDescriptions: mockTagDescriptions,
        data: {},
        expandedNodes: {},
        denyTags: [],
        blueprints: [],
        paging: null,
        autoload: false,
        search_models: false,
        search_blueprints: false,
        searchTerm: null,
        initialSetupComplete: true,
        fetchData: jest.fn(),
        setData: jest.fn(),
        toggleNode: jest.fn(),
        addAllTags: jest.fn(),
        clearTags: jest.fn(),
        addDenyTag: jest.fn(),
        removeDenyTag: jest.fn(),
        setTagState: jest.fn(),
        fetchBlueprints: jest.fn(),
        setBlueprints: jest.fn(),
        setSearchTerm: jest.fn(),
        fetchTagDescriptions: jest.fn(),
        setInitialSetupComplete: jest.fn(),
      })
    );
    jest.clearAllMocks();
  });

  it('renders all main sections and example tags', () => {
    render(<InstructionsPartSearch />);
    expect(screen.getByText('Instructions (Part Search)')).toBeInTheDocument();
    expect(screen.getByText('Build')).toBeInTheDocument();
    expect(screen.getByText('Component')).toBeInTheDocument();
    expect(screen.getByText('Connection')).toBeInTheDocument();
    expect(screen.getByText('Decoration')).toBeInTheDocument();
    expect(screen.getByText('Texture')).toBeInTheDocument();
    expect(screen.getByText('build|separate wall')).toBeInTheDocument();
    expect(screen.getByText('component|door|arched')).toBeInTheDocument();
    expect(screen.getByText('texture|dungeon_stone')).toBeInTheDocument();
  });

  it('shows tag description tooltip on hover (with delay)', async () => {
    jest.useFakeTimers();
    render(<InstructionsPartSearch />);
    const tagBtn = screen.getByText('build|separate wall');
    fireEvent.mouseEnter(tagBtn);
    await act(async () => {
      jest.advanceTimersByTime(500);
    });
    expect(await screen.findByText('Separate wall desc')).toBeInTheDocument();
    fireEvent.mouseLeave(tagBtn);
    act(() => {
      jest.runAllTimers();
    });
    // Tooltip should disappear after mouse leave
    expect(screen.queryByText('Separate wall desc')).not.toBeInTheDocument();
    jest.useRealTimers();
  });

  it('shows section description if present', () => {
    render(<InstructionsPartSearch />);
    expect(screen.getByText('Build description')).toBeInTheDocument();
  });

  it('calls addTag and removeTag correctly when clicking example tag', () => {
    (useTagContext as jest.Mock).mockImplementation((selector: (state: TagStore) => unknown) =>
      selector({
        addTag: mockAddTag,
        removeTag: mockRemoveTag,
        selectedTags: ['build|s2w', 'build|separate wall'],
        tagDescriptions: mockTagDescriptions,
        data: {},
        expandedNodes: {},
        denyTags: [],
        blueprints: [],
        paging: null,
        autoload: false,
        search_models: false,
        search_blueprints: false,
        searchTerm: null,
        initialSetupComplete: true,
        fetchData: jest.fn(),
        setData: jest.fn(),
        toggleNode: jest.fn(),
        addAllTags: jest.fn(),
        clearTags: jest.fn(),
        addDenyTag: jest.fn(),
        removeDenyTag: jest.fn(),
        setTagState: jest.fn(),
        fetchBlueprints: jest.fn(),
        setBlueprints: jest.fn(),
        setSearchTerm: jest.fn(),
        fetchTagDescriptions: jest.fn(),
        setInitialSetupComplete: jest.fn(),
      })
    );
    render(<InstructionsPartSearch />);
    const tagBtn = screen.getByText('build|s2w');
    fireEvent.click(tagBtn);
    // Should call removeTag for 'build|s2w' and 'build|separate wall', then addTag for clicked
    expect(mockRemoveTag).toHaveBeenCalledWith('build|s2w');
    expect(mockRemoveTag).toHaveBeenCalledWith('build|separate wall');
    expect(mockAddTag).toHaveBeenCalledWith('build|s2w');
  });
});
