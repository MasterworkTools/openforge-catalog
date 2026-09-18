import React from 'react';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import TagRow from '../tag-row';
import { useTagContext } from '@/contexts/tag-context';
import type { TagStore } from '@/stores/tag-store';

jest.mock('@/contexts/tag-context', () => ({
  useTagContext: jest.fn(),
}));

const mockUseTagContext = useTagContext as jest.MockedFunction<typeof useTagContext>;

describe('TagRow', () => {
  const mockTagDescriptions = {
    'tag1': 'Description for tag1',
    'tag2': 'Description for tag2',
    'texture|stone': 'Stone texture description'
  };

  const mockOnTagClick = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
    jest.useFakeTimers();

    mockUseTagContext.mockImplementation((selector) => {
      const state: TagStore = {
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
        tagDescriptions: mockTagDescriptions,
        initialSetupComplete: true,
        fetchData: jest.fn(),
        setData: jest.fn(),
        toggleNode: jest.fn(),
        addTag: jest.fn(),
        addAllTags: jest.fn(),
        removeTag: jest.fn(),
        clearTags: jest.fn(),
        addDenyTag: jest.fn(),
        removeDenyTag: jest.fn(),
        setTagState: jest.fn(),
        fetchBlueprints: jest.fn(),
        setBlueprints: jest.fn(),
        setSearchTerm: jest.fn(),
        fetchTagDescriptions: jest.fn(),
        setInitialSetupComplete: jest.fn(),
      };
      return selector(state);
    });
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  it('renders tags with click handlers', () => {
    const tags = ['tag1', 'tag2', 'texture|stone'];

    render(<TagRow tags={tags} onTagClick={mockOnTagClick} />);

    const tagButtons = screen.getAllByRole('button');
    const tag1Button = tagButtons.find(button => button.textContent?.includes('tag1'));
    const tag2Button = tagButtons.find(button => button.textContent?.includes('tag2'));

    expect(tag1Button).toBeInTheDocument();
    expect(tag2Button).toBeInTheDocument();

    fireEvent.click(tag1Button!);
    expect(mockOnTagClick).toHaveBeenCalledWith('tag1');
  });

  it('shows tag descriptions on hover', async () => {
    const tags = ['tag1', 'tag2'];

    render(<TagRow tags={tags} onTagClick={mockOnTagClick} />);

    const tagButton = screen.getByText('tag1');
    fireEvent.mouseEnter(tagButton);

    // Fast-forward timers to trigger the 500ms delay
    act(() => {
      jest.advanceTimersByTime(500);
    });

    await waitFor(() => {
      expect(screen.getByText('Description for tag1')).toBeInTheDocument();
    });
  });

  it('hides tooltip when mouse leaves', async () => {
    const tags = ['tag1'];

    render(<TagRow tags={tags} onTagClick={mockOnTagClick} />);

    const tagButton = screen.getByText('tag1');
    fireEvent.mouseEnter(tagButton);
    act(() => {
      jest.advanceTimersByTime(500);
    });

    await waitFor(() => {
      expect(screen.getByText('Description for tag1')).toBeInTheDocument();
    });

    fireEvent.mouseLeave(tagButton);

    await waitFor(() => {
      expect(screen.queryByText('Description for tag1')).not.toBeInTheDocument();
    });
  });

  it('shows tooltip above when tooltipAbove is true', async () => {
    const tags = ['tag1'];

    render(<TagRow tags={tags} onTagClick={mockOnTagClick} tooltipAbove={true} />);

    const tagButton = screen.getByText('tag1');
    fireEvent.mouseEnter(tagButton);
    act(() => {
      jest.advanceTimersByTime(500);
    });

    await waitFor(() => {
      const tooltip = screen.getByText('Description for tag1');
      expect(tooltip).toBeInTheDocument();
      expect(tooltip).toHaveClass('bottom-full');
    });
  });

  it('shows tooltip below when tooltipAbove is false', async () => {
    const tags = ['tag1'];

    render(<TagRow tags={tags} onTagClick={mockOnTagClick} tooltipAbove={false} />);

    const tagButton = screen.getByText('tag1');
    fireEvent.mouseEnter(tagButton);
    act(() => {
      jest.advanceTimersByTime(500);
    });

    await waitFor(() => {
      const tooltip = screen.getByText('Description for tag1');
      expect(tooltip).toBeInTheDocument();
      expect(tooltip).toHaveClass('top-full');
    });
  });

  it('handles empty tags array', () => {
    render(<TagRow tags={[]} onTagClick={mockOnTagClick} />);

    const buttons = screen.queryAllByRole('button');
    expect(buttons).toHaveLength(0);
  });

  it('cleans up timeout on unmount', () => {
    const tags = ['tag1'];
    const clearTimeoutSpy = jest.spyOn(global, 'clearTimeout');

    const { unmount } = render(<TagRow tags={tags} onTagClick={mockOnTagClick} />);

    const tagButton = screen.getByText('tag1');
    fireEvent.mouseEnter(tagButton);

    unmount();

    expect(clearTimeoutSpy).toHaveBeenCalled();
    clearTimeoutSpy.mockRestore();
  });
});
