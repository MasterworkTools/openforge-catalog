import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import ResultsContainer from '../results-container';
import { useBlueprintContext } from '@/contexts/blueprint-context';
import { useTagContext } from '@/contexts/tag-context';
import type { BlueprintStore } from '@/stores/blueprint-store';
import type { TagStore } from '@/stores/tag-store';
import type { Blueprint, Paging } from '@/types';
import { createMockBlueprint, createMockPaging, createMockConfigTags, createMockFunctions, setupTestEnvironment, cleanupTestEnvironment } from '@/test-utils';

jest.mock('@/contexts/blueprint-context', () => ({
  useBlueprintContext: jest.fn(),
}));
jest.mock('@/contexts/tag-context', () => ({
  useTagContext: jest.fn(),
}));

// Mock clipboard API
Object.assign(navigator, {
  clipboard: {
    writeText: jest.fn(),
  },
});

describe('ResultsContainer', () => {
  const mockFunctions = createMockFunctions();
  const blueprints: Blueprint[] = [
    createMockBlueprint({ id: '1', blueprint_name: 'BP1' }),
    createMockBlueprint({ id: '2', blueprint_name: 'BP2' }),
  ];
  const paging: Paging = createMockPaging();

  beforeEach(() => {
    setupTestEnvironment();

    (useBlueprintContext as jest.Mock).mockImplementation((selector: (state: BlueprintStore) => unknown) =>
      selector({
        setSelectedBlueprint: mockFunctions.setSelectedBlueprint,
        selectedBlueprint: null,
        configSelections: {},
        setConfigSelection: mockFunctions.setConfigSelection,
        fetchBlueprintById: mockFunctions.fetchBlueprintById,
        fetchBlueprintByMd5: mockFunctions.fetchBlueprintByMd5,
        clearConfigSelections: mockFunctions.clearConfigSelections,
      })
    );
    (useTagContext as jest.Mock).mockImplementation((selector: (state: TagStore) => unknown) =>
      selector({
        blueprints,
        paging,
        selectedTags: ['foo', 'bar'],
        denyTags: ['baz'],
        searchTerm: 'search',
        removeTag: mockFunctions.removeTag,
        addTag: mockFunctions.addTag,
        clearTags: mockFunctions.clearTags,
        fetchBlueprints: mockFunctions.fetchBlueprints,
        setTagState: mockFunctions.setTagState,
        autoload: false,
        setSearchTerm: mockFunctions.setSearchTerm,
        data: {},
        expandedNodes: {},
        tagDescriptions: {},
        fetchData: mockFunctions.fetchData,
        setData: mockFunctions.setData,
        toggleNode: mockFunctions.toggleNode,
        addAllTags: mockFunctions.addAllTags,
        addDenyTag: mockFunctions.addDenyTag,
        removeDenyTag: mockFunctions.removeDenyTag,
        setBlueprints: mockFunctions.setBlueprints,
        fetchTagDescriptions: mockFunctions.fetchTagDescriptions,
        search_models: false,
        search_blueprints: false,
        initialSetupComplete: true,
        setInitialSetupComplete: mockFunctions.setInitialSetupComplete,
      })
    );
  });

  afterEach(() => {
    cleanupTestEnvironment();
  });

  it('renders complete results container with all sections', () => {
    render(<ResultsContainer />);

    expect(screen.getByText('Blueprints')).toBeInTheDocument();
    expect(screen.getByText('foo')).toBeInTheDocument();
    expect(screen.getByText('bar')).toBeInTheDocument();
    expect(screen.getByText('baz')).toBeInTheDocument();
    expect(screen.getByText('search')).toBeInTheDocument();
    expect(screen.getByText('BP1')).toBeInTheDocument();
    expect(screen.getByText('BP2')).toBeInTheDocument();

    const totalCountDiv = screen.getByText((content, element) =>
      element?.className === 'totalCount'
    );
    expect(totalCountDiv).toBeInTheDocument();
    expect((totalCountDiv.textContent || '').replace(/\s+/g, ' ')).toContain('1 - 2 of 10 that match your tags');
  });

  it('handles tag removal integration', () => {
    render(<ResultsContainer />);

    const fooButton = screen.getAllByRole('button').find(btn => btn.parentElement?.textContent?.includes('foo'));
    if (fooButton) fireEvent.click(fooButton);

    expect(mockFunctions.removeTag).toHaveBeenCalled();
  });

  it('handles search term removal integration', () => {
    render(<ResultsContainer />);

    const searchButton = screen.getAllByRole('button').find(btn => btn.parentElement?.textContent?.includes('search'));
    if (searchButton) fireEvent.click(searchButton);

    expect(mockFunctions.setSearchTerm).toHaveBeenCalledWith(null);
  });

  it('handles clear functionality integration', () => {
    render(<ResultsContainer />);

    fireEvent.click(screen.getByText('clear'));

    expect(mockFunctions.clearTags).toHaveBeenCalled();
    expect(mockFunctions.setSelectedBlueprint).toHaveBeenCalledWith(null);
  });

  it('handles blueprint selection integration', () => {
    render(<ResultsContainer />);

    fireEvent.click(screen.getByText('BP1'));

    expect(mockFunctions.setSelectedBlueprint).toHaveBeenCalledWith(blueprints[0]);
  });

  it('handles pagination integration', () => {
    (useTagContext as jest.Mock).mockImplementation((selector: (state: TagStore) => unknown) =>
      selector({
        blueprints,
        paging: createMockPaging({ total_count: 10, start_count: 2 }),
        selectedTags: ['foo', 'bar'],
        denyTags: ['baz'],
        searchTerm: 'search',
        removeTag: mockFunctions.removeTag,
        addTag: mockFunctions.addTag,
        clearTags: mockFunctions.clearTags,
        fetchBlueprints: mockFunctions.fetchBlueprints,
        setTagState: mockFunctions.setTagState,
        autoload: false,
        setSearchTerm: mockFunctions.setSearchTerm,
        data: {},
        expandedNodes: {},
        tagDescriptions: {},
        fetchData: mockFunctions.fetchData,
        setData: mockFunctions.setData,
        toggleNode: mockFunctions.toggleNode,
        addAllTags: mockFunctions.addAllTags,
        addDenyTag: mockFunctions.addDenyTag,
        removeDenyTag: mockFunctions.removeDenyTag,
        setBlueprints: mockFunctions.setBlueprints,
        fetchTagDescriptions: mockFunctions.fetchTagDescriptions,
        search_models: false,
        search_blueprints: false,
        initialSetupComplete: true,
        setInitialSetupComplete: mockFunctions.setInitialSetupComplete,
      })
    );

    render(<ResultsContainer />);

    fireEvent.click(screen.getByText('Next Page'));
    expect(mockFunctions.fetchBlueprints).toHaveBeenCalledWith({ next: 'next-token' });

    fireEvent.click(screen.getByText('Previous Page'));
    expect(mockFunctions.fetchBlueprints).toHaveBeenCalledWith({ previous: 'prev-token' });
  });

  it('handles configValues integration', () => {
    const configValues = createMockConfigTags({
      require: [{ tag: 'required1' }, { tag: 'required2' }],
      deny: [{ tag: 'denied1' }, { tag: 'denied2' }],
    });

    // Mock fetchData to return undefined (synchronous)
    mockFunctions.fetchData.mockReturnValue(undefined);

    render(<ResultsContainer configValues={configValues} />);

    expect(mockFunctions.setTagState).toHaveBeenCalledWith({
      require: ['required1', 'required2'],
      deny: ['denied1', 'denied2']
    });
  });

  it('handles configValues with constrain logic integration', () => {
    const configValues = createMockConfigTags({
      require: [],
      deny: [],
      constrain: [
        { tag: 'base' },
        { filter: 'base|level1' },
        { filter: 'base|level2' }
      ]
    });

    // Mock fetchData to return undefined (synchronous)
    mockFunctions.fetchData.mockReturnValue(undefined);

    render(<ResultsContainer
      configValues={configValues}
      parentTags={[]}
      siblingSelections={[
        { partName: 'test-part', tags: ['base|level1|sub', 'base|level3|sub', 'other|tag'] }
      ]}
    />);

    expect(mockFunctions.setTagState).toHaveBeenCalledWith({
      require: ['base|level3|sub'], // Should include this as it starts with 'base' but doesn't match any filter
      deny: []
    });
  });

  it('handles configValues with async fetchData without race condition', async () => {
    const configValues = createMockConfigTags({
      require: [{ tag: 'required1' }, { tag: 'required2' }],
      deny: [{ tag: 'denied1' }],
    });

    // Mock fetchData to return a Promise that resolves after a state update
    // This simulates the race condition where fetchData updates state (like setSearchTerm)
    // which causes the effect to re-run and potentially cancel the original effect
    const mockFetchData = jest.fn(() => Promise.resolve());

    (useTagContext as jest.Mock).mockImplementation((selector: (state: TagStore) => unknown) =>
      selector({
        blueprints,
        paging,
        selectedTags: [],
        denyTags: [],
        searchTerm: null,
        removeTag: mockFunctions.removeTag,
        addTag: mockFunctions.addTag,
        clearTags: mockFunctions.clearTags,
        fetchBlueprints: mockFunctions.fetchBlueprints,
        setTagState: mockFunctions.setTagState,
        autoload: false,
        setSearchTerm: mockFunctions.setSearchTerm,
        data: {},
        expandedNodes: {},
        tagDescriptions: {},
        fetchData: mockFetchData,
        setData: mockFunctions.setData,
        toggleNode: mockFunctions.toggleNode,
        addAllTags: mockFunctions.addAllTags,
        addDenyTag: mockFunctions.addDenyTag,
        removeDenyTag: mockFunctions.removeDenyTag,
        setBlueprints: mockFunctions.setBlueprints,
        fetchTagDescriptions: mockFunctions.fetchTagDescriptions,
        search_models: false,
        search_blueprints: false,
        initialSetupComplete: true,
        setInitialSetupComplete: mockFunctions.setInitialSetupComplete,
      })
    );

    render(<ResultsContainer configValues={configValues} />);

    // Wait for async operations to complete and verify setTagState was called
    // This ensures the race condition fix is working - even though fetchData
    // may trigger state updates that cause the effect to re-run, the original
    // effect should still complete and set the tags
    await waitFor(() => {
      expect(mockFunctions.setTagState).toHaveBeenCalledWith({
        require: ['required1', 'required2'],
        deny: ['denied1']
      });
    });
  });

  it('handles copy to clipboard integration', () => {
    // Mock navigator.clipboard.writeText
    const mockWriteText = jest.fn();
    Object.assign(navigator, {
      clipboard: {
        writeText: mockWriteText,
      },
    });

    // Set up context with selected tags and search term
    (useTagContext as jest.Mock).mockImplementation((selector: (state: TagStore) => unknown) =>
      selector({
        blueprints,
        paging,
        selectedTags: ['foo', 'bar'],
        denyTags: [],
        searchTerm: 'search',
        removeTag: mockFunctions.removeTag,
        addTag: mockFunctions.addTag,
        clearTags: mockFunctions.clearTags,
        fetchBlueprints: mockFunctions.fetchBlueprints,
        setTagState: mockFunctions.setTagState,
        autoload: false,
        setSearchTerm: mockFunctions.setSearchTerm,
        data: {},
        expandedNodes: {},
        tagDescriptions: {},
        fetchData: mockFunctions.fetchData,
        setData: mockFunctions.setData,
        toggleNode: mockFunctions.toggleNode,
        addAllTags: mockFunctions.addAllTags,
        addDenyTag: mockFunctions.addDenyTag,
        removeDenyTag: mockFunctions.removeDenyTag,
        setBlueprints: mockFunctions.setBlueprints,
        fetchTagDescriptions: mockFunctions.fetchTagDescriptions,
        search_models: false,
        search_blueprints: false,
        initialSetupComplete: true,
        setInitialSetupComplete: mockFunctions.setInitialSetupComplete,
      })
    );

    render(<ResultsContainer />);

    const copyButton = screen.getByTitle('Copy url to clipboard');
    fireEvent.click(copyButton);

    expect(mockWriteText).toHaveBeenCalledWith('http://localhost/?tag=foo&tag=bar&search=search');
  });

  it('handles tag removability logic integration', () => {
    const configValues = createMockConfigTags({
      require: [{ tag: 'config-required' }],
      deny: [{ tag: 'config-denied' }],
    });

    (useTagContext as jest.Mock).mockImplementation((selector: (state: TagStore) => unknown) =>
      selector({
        blueprints,
        paging,
        selectedTags: ['config-required', 'config-denied', 'removable-tag'],
        denyTags: ['config-denied'],
        searchTerm: null,
        removeTag: mockFunctions.removeTag,
        addTag: mockFunctions.addTag,
        clearTags: mockFunctions.clearTags,
        fetchBlueprints: mockFunctions.fetchBlueprints,
        setTagState: mockFunctions.setTagState,
        autoload: false,
        setSearchTerm: mockFunctions.setSearchTerm,
        data: {},
        expandedNodes: {},
        tagDescriptions: {},
        fetchData: mockFunctions.fetchData,
        setData: mockFunctions.setData,
        toggleNode: mockFunctions.toggleNode,
        addAllTags: mockFunctions.addAllTags,
        addDenyTag: mockFunctions.addDenyTag,
        removeDenyTag: mockFunctions.removeDenyTag,
        setBlueprints: mockFunctions.setBlueprints,
        fetchTagDescriptions: mockFunctions.fetchTagDescriptions,
        search_models: false,
        search_blueprints: false,
        initialSetupComplete: true,
        setInitialSetupComplete: mockFunctions.setInitialSetupComplete,
      })
    );

    render(<ResultsContainer configValues={configValues} />);

    // Check that config-required tags don't have remove buttons
    const configRequiredTag = screen.getByText('config-required');
    // Look for button only within the same list item, not the entire parent
    const removeButton = configRequiredTag.closest('li')?.querySelector('button');
    expect(removeButton).not.toBeInTheDocument();

    // Check that removable tags do have remove buttons
    const removableTag = screen.getByText('removable-tag');
    const removableButton = removableTag.closest('li')?.querySelector('button');
    expect(removableButton).toBeInTheDocument();
  });

  it('handles selected blueprint highlighting integration', () => {
    const selectedBlueprint = createMockBlueprint({ id: '1', blueprint_name: 'BP1' });

    (useBlueprintContext as jest.Mock).mockImplementation((selector: (state: BlueprintStore) => unknown) =>
      selector({
        setSelectedBlueprint: mockFunctions.setSelectedBlueprint,
        selectedBlueprint,
        configSelections: {},
        setConfigSelection: mockFunctions.setConfigSelection,
        fetchBlueprintById: mockFunctions.fetchBlueprintById,
        fetchBlueprintByMd5: mockFunctions.fetchBlueprintByMd5,
        clearConfigSelections: mockFunctions.clearConfigSelections,
      })
    );

    render(<ResultsContainer />);

    const selectedItem = screen.getByText('BP1').closest('li');
    expect(selectedItem).toHaveClass('selected');
  });

  it('handles empty blueprints list integration', () => {
    (useTagContext as jest.Mock).mockImplementation((selector: (state: TagStore) => unknown) =>
      selector({
        blueprints: [],
        paging: createMockPaging({ total_count: 0, start_count: 0, next_token: undefined, previous_token: undefined }),
        selectedTags: [],
        denyTags: [],
        searchTerm: null,
        removeTag: mockFunctions.removeTag,
        addTag: mockFunctions.addTag,
        clearTags: mockFunctions.clearTags,
        fetchBlueprints: mockFunctions.fetchBlueprints,
        setTagState: mockFunctions.setTagState,
        autoload: false,
        setSearchTerm: mockFunctions.setSearchTerm,
        data: {},
        expandedNodes: {},
        tagDescriptions: {},
        fetchData: mockFunctions.fetchData,
        setData: mockFunctions.setData,
        toggleNode: mockFunctions.toggleNode,
        addAllTags: mockFunctions.addAllTags,
        addDenyTag: mockFunctions.addDenyTag,
        removeDenyTag: mockFunctions.removeDenyTag,
        setBlueprints: mockFunctions.setBlueprints,
        fetchTagDescriptions: mockFunctions.fetchTagDescriptions,
        search_models: false,
        search_blueprints: false,
        initialSetupComplete: true,
        setInitialSetupComplete: mockFunctions.setInitialSetupComplete,
      })
    );

    render(<ResultsContainer />);

    const totalCountDiv = screen.getByText((content, element) =>
      element?.className === 'totalCount'
    );
    expect(totalCountDiv.textContent).toContain('1 - 0 of 0');
  });
});
