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
        denyChildrenTags: [],
        allowTags: [],
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
        denyChildrenTags: [],
        allowTags: [],
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

  it('keeps deny_children and allow when the props change after setup', () => {
    // The sweep is what keeps arrow slits and curved corners out of a
    // plain wall's dialog. It was passed on the initial setup and
    // then dropped by the rebuild on every later prop change, which
    // *widens* the result set — the one direction a restriction must
    // never fail in.
    const configValues = createMockConfigTags({
      require: [{ tag: 'shape|wall' }],
      deny: [],
      deny_children: [{ tag: 'component' }],
      allow: [{ tag: 'component|wall' }]
    });
    mockFunctions.fetchData.mockReturnValue(undefined);

    const { rerender } = render(<ResultsContainer configValues={configValues} />);
    mockFunctions.setTagState.mockClear();
    // A second render with different props takes the update branch,
    // which is the one that used to lose them.
    rerender(
      <ResultsContainer configValues={configValues} parentTags={['texture|cave']} />
    );

    expect(mockFunctions.setTagState).toHaveBeenCalledWith(
      expect.objectContaining({
        denyChildren: ['component'],
        allow: ['component|wall']
      })
    );
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

  it('lets the caller name seeded tags the person may take off', () => {
    // `removable` is what makes the guide's dialog open narrow and
    // still let you widen it. Deleting the whole branch that reads it
    // left the suite green, because nothing passed the prop at all.
    // Both tags are seeded by the caller, so both are normally fixed.
    // The store already holds them as the selected set, which is what
    // the list actually renders.
    const configValues = createMockConfigTags({
      require: [{ tag: 'foo' }, { tag: 'bar' }],
      deny: []
    });
    mockFunctions.fetchData.mockReturnValue(undefined);

    const { rerender } = render(
      <ResultsContainer configValues={configValues} removable={['foo']} />
    );
    const withProp = screen.queryAllByRole('button', { name: '-' }).length;

    // The same seeded tags, minus the caller's permission. The store
    // holds other tags that are removable for their own reasons, so
    // the difference is what this prop is responsible for.
    rerender(<ResultsContainer configValues={configValues} removable={[]} />);
    const without = screen.queryAllByRole('button', { name: '-' }).length;

    expect(withProp - without).toBe(1);
  });

  it('writes a change confined to deny_children and allow', () => {
    // The store already holds the require/deny this config derives,
    // so the old change test — which compared only those two — saw no
    // change and dropped the sweep on the floor. The previous
    // regression test could not catch it: `setTagState` is mocked, so
    // `selectedTags` never caught up and `requireChanged` was true on
    // every render regardless.
    (useTagContext as jest.Mock).mockImplementation(
      (selector: (state: TagStore) => unknown) =>
        selector({
          blueprints,
          paging,
          // Already equal to what this config derives.
          selectedTags: ['shape|wall'],
          denyTags: [],
          // And the sweep is not yet applied, which is the change.
          denyChildrenTags: [],
          allowTags: [],
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
        } as unknown as TagStore)
    );
    const configValues = createMockConfigTags({
      require: [{ tag: 'shape|wall' }],
      deny: [],
      deny_children: [{ tag: 'component' }],
      allow: [{ tag: 'component|wall' }]
    });
    mockFunctions.fetchData.mockReturnValue(undefined);

    const { rerender } = render(<ResultsContainer configValues={configValues} />);
    mockFunctions.setTagState.mockClear();
    rerender(
      <ResultsContainer configValues={configValues} parentTags={['texture|cave']} />
    );

    expect(mockFunctions.setTagState).toHaveBeenCalledWith(
      expect.objectContaining({
        denyChildren: ['component'],
        allow: ['component|wall']
      })
    );
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
        denyChildrenTags: [],
        allowTags: [],
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
        denyChildrenTags: [],
        allowTags: [],
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
        denyChildrenTags: [],
        allowTags: [],
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
        denyChildrenTags: [],
        allowTags: [],
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
