import React from 'react';
import { render, screen, fireEvent, act } from '@testing-library/react';
import TagContainer from '../tag-container';
import { useTagContext } from '@/contexts/tag-context';
import type { TagStore } from '@/stores/tag-store';

jest.mock('@/contexts/tag-context', () => ({
  useTagContext: jest.fn(),
}));
jest.mock('../tag-container.css', () => ({}));

const mockData = {
  foo: {
    __name: 'foo',
    __subTags: 1,
    __count: 2,
    children: {
      bar: {
        __name: 'bar',
        __subTags: 0,
        __count: 1,
        children: {},
      },
    },
  },
  baz: {
    __name: 'baz',
    __subTags: 0,
    __count: 0,
    children: {},
  },
};

const mockTagDescriptions = {
  foo: 'Foo description',
  bar: 'Bar description',
};

describe('TagContainer', () => {
  const mockToggleNode = jest.fn();
  const mockAddTag = jest.fn();
  const mockAddDenyTag = jest.fn();
  const mockSetSearchTerm = jest.fn();
  const mockFetchTagDescriptions = jest.fn();

  const createMockState = (overrides = {}) => ({
    data: mockData,
    expandedNodes: { '0-foo': true },
    toggleNode: mockToggleNode,
    addTag: mockAddTag,
    addDenyTag: mockAddDenyTag,
    setSearchTerm: mockSetSearchTerm,
    searchTerm: '',
    tagDescriptions: mockTagDescriptions,
    fetchTagDescriptions: mockFetchTagDescriptions,
    selectedTags: [],
    denyTags: [],
    blueprints: [],
    paging: null,
    autoload: false,
    search_models: false,
    search_blueprints: false,
    initialSetupComplete: true,
    fetchData: jest.fn(),
    setData: jest.fn(),
    addAllTags: jest.fn(),
    removeTag: jest.fn(),
    clearTags: jest.fn(),
    removeDenyTag: jest.fn(),
    setTagState: jest.fn(),
    fetchBlueprints: jest.fn(),
    setBlueprints: jest.fn(),
    setInitialSetupComplete: jest.fn(),
    ...overrides,
  });

  beforeEach(() => {
    (useTagContext as jest.Mock).mockImplementation((selector: (state: TagStore) => unknown) =>
      selector(createMockState())
    );
    jest.clearAllMocks();
    jest.useFakeTimers();
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  it('renders tags and nested tags', () => {
    render(<TagContainer />);
    expect(screen.getAllByText((c, el) => el?.textContent?.includes('foo') || false)[0]).toBeInTheDocument();
    expect(screen.getAllByText((c, el) => el?.textContent?.includes('bar') || false)[0]).toBeInTheDocument();
    expect(screen.getAllByText((c, el) => el?.textContent?.includes('baz') || false)[0]).toBeInTheDocument();
    expect(screen.getByText('Browse Tags')).toBeInTheDocument();
  });

  it('expands/collapses nodes', () => {
    render(<TagContainer />);
    const expandButton = screen.getByLabelText('collapse tag');
    fireEvent.click(expandButton);
    expect(mockToggleNode).toHaveBeenCalledWith('0-foo');
  });

  it('calls addTag when + is clicked', () => {
    render(<TagContainer />);
    const plusButtons = screen.getAllByText('+');
    fireEvent.click(plusButtons[0]);
    expect(mockAddTag).toHaveBeenCalledWith('foo');
  });

  it('calls addDenyTag when - is clicked', () => {
    render(<TagContainer />);
    const minusButtons = screen.getAllByText('-');
    fireEvent.click(minusButtons[0]);
    expect(mockAddDenyTag).toHaveBeenCalledWith('foo');
  });

  it('renders both + and - buttons together', () => {
    render(<TagContainer />);
    const plusButtons = screen.getAllByText('+');
    const minusButtons = screen.getAllByText('-');
    expect(plusButtons.length).toBeGreaterThan(0);
    expect(minusButtons.length).toBeGreaterThan(0);
    expect(plusButtons.length).toBe(minusButtons.length);
  });

  it('renders - button with red color and bold styling', () => {
    render(<TagContainer />);
    const minusButtons = screen.getAllByText('-');
    const firstMinusButton = minusButtons[0];
    expect(firstMinusButton).toHaveClass('font-bold');
    expect(firstMinusButton).toHaveClass('text-red-600');
    expect(firstMinusButton).toHaveClass('cursor-pointer');
  });

  it('renders + button with bold styling', () => {
    render(<TagContainer />);
    const plusButtons = screen.getAllByText('+');
    const firstPlusButton = plusButtons[0];
    expect(firstPlusButton).toHaveClass('font-bold');
    expect(firstPlusButton).toHaveClass('cursor-pointer');
  });

  it('renders buttons with aria-labels for accessibility', () => {
    render(<TagContainer />);
    const addButton = screen.getByLabelText('Add tag foo');
    const excludeButton = screen.getByLabelText('Exclude tag foo');
    expect(addButton).toBeInTheDocument();
    expect(excludeButton).toBeInTheDocument();
  });

  it('shows tooltip with delay when hovering over tag with description', async () => {
    const testTagDescriptions = { 'test-tag': 'Test description' };
    const testData = {
      'test-tag': {
        __name: 'test-tag',
        __count: 5,
        __subTags: 0,
        children: {}
      }
    };

    (useTagContext as jest.Mock).mockImplementation((selector: (state: TagStore) => unknown) =>
      selector(createMockState({
        data: testData,
        expandedNodes: {},
        searchTerm: null,
        tagDescriptions: testTagDescriptions,
      }))
    );

    render(<TagContainer />);

    const tagElement = screen.getByText('test-tag');
    fireEvent.mouseEnter(tagElement);

    // Wait for tooltip to appear after delay
    const tooltip = await screen.findByText('Test description');
    expect(tooltip).toBeInTheDocument();
  });

  it('searches and sets searchTerm on input', () => {
    render(<TagContainer />);
    const input = screen.getByPlaceholderText('Search blueprints...');
    fireEvent.change(input, { target: { value: 'test' } });
    act(() => {
      jest.advanceTimersByTime(300);
    });
    expect(mockSetSearchTerm).toHaveBeenCalledWith('test');
  });

  it('sets searchTerm to null on empty input', () => {
    render(<TagContainer />);
    const input = screen.getByPlaceholderText('Search blueprints...');
    fireEvent.change(input, { target: { value: '' } });
    act(() => {
      jest.advanceTimersByTime(300);
    });
    expect(mockSetSearchTerm).toHaveBeenCalledWith(null);
  });

  it('sets searchTerm on Enter key', () => {
    render(<TagContainer />);
    const input = screen.getByPlaceholderText('Search blueprints...');
    fireEvent.change(input, { target: { value: 'foo' } });
    fireEvent.keyDown(input, { key: 'Enter' });
    expect(mockSetSearchTerm).toHaveBeenCalledWith('foo');
  });

  it('fetches tag descriptions on mount', () => {
    render(<TagContainer />);
    expect(mockFetchTagDescriptions).toHaveBeenCalled();
  });

  it('syncs searchInput with searchTerm from store', () => {
    (useTagContext as jest.Mock).mockImplementation((selector: (state: TagStore) => unknown) =>
      selector(createMockState({
        expandedNodes: {},
        searchTerm: 'preset',
      }))
    );
    render(<TagContainer />);
    expect(screen.getByDisplayValue('preset')).toBeInTheDocument();
  });

  it('handles no tags gracefully', () => {
    (useTagContext as jest.Mock).mockImplementation((selector: (state: TagStore) => unknown) =>
      selector(createMockState({
        data: {},
        expandedNodes: {},
        tagDescriptions: {},
      }))
    );
    render(<TagContainer />);
    expect(screen.getByText('Browse Tags')).toBeInTheDocument();
  });

  it('handles tag with no description', () => {
    (useTagContext as jest.Mock).mockImplementation((selector: (state: TagStore) => unknown) =>
      selector(createMockState({
        data: {
          node: { __name: 'node', __subTags: 0, __count: 1, children: {} },
        },
        expandedNodes: {},
        tagDescriptions: {},
      }))
    );
    render(<TagContainer />);
    expect(screen.getByText('node')).toBeInTheDocument();
  });
});
