import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import BlueprintContainer from '../blueprint-container';
import { Blueprint, ConfigPart } from '@/types';
import type { BlueprintStore } from '@/stores/blueprint-store';
import type { TagStore } from '@/stores/tag-store';

// Mock the contexts
jest.mock('@/contexts/blueprint-context', () => ({
  useBlueprintContext: jest.fn(),
}));

jest.mock('@/contexts/tag-context', () => ({
  useTagContext: jest.fn(),
}));

// Mock utilities
jest.mock('@/utils/format', () => ({
  formatFileSize: jest.fn((size) => `${size} bytes`),
}));

jest.mock('@/utils/blueprint-utils', () => ({
  ...jest.requireActual('@/utils/blueprint-utils'),
  downloadFiles: jest.fn(),
}));

jest.mock('new-github-issue-url', () => jest.fn(() => 'https://github.com/devonjones/openforge_catalog/issues/new'));

// Mock ConfigBox component
jest.mock('../blueprint/config-box', () => {
  return function MockConfigBox({ title }: { title: string; value: unknown }) {
    return <div data-testid={`config-box-${title}`}>{title}</div>;
  };
});

import { useBlueprintContext } from '@/contexts/blueprint-context';
import { useTagContext } from '@/contexts/tag-context';
import { downloadFiles } from '@/utils/blueprint-utils';

const mockUseBlueprintContext = useBlueprintContext as jest.MockedFunction<typeof useBlueprintContext>;
const mockUseTagContext = useTagContext as jest.MockedFunction<typeof useTagContext>;
const mockDownloadFiles = downloadFiles as jest.MockedFunction<typeof downloadFiles>;

// Mock window.location and navigator
const mockClipboard = {
  writeText: jest.fn(),
};
Object.defineProperty(navigator, 'clipboard', {
  value: mockClipboard,
  writable: true,
});

const mockHistory = {
  replaceState: jest.fn(),
};
Object.defineProperty(window, 'history', {
  value: mockHistory,
  writable: true,
});

const mockAddEventListener = jest.fn();
const mockRemoveEventListener = jest.fn();
Object.defineProperty(window, 'addEventListener', {
  value: mockAddEventListener,
  writable: true,
});
Object.defineProperty(window, 'removeEventListener', {
  value: mockRemoveEventListener,
  writable: true,
});

describe('BlueprintContainer', () => {
  const mockBlueprint: Blueprint = {
    id: '123',
    blueprint_name: 'Test Blueprint',
    blueprint_type: 'model',
    file_name: 'test.stl',
    file_md5: 'abc123',
    file_size: 1024,
    file_modified_at: '2023-01-01T00:00:00Z',
    full_name: 'Test Blueprint Full Name',
    created_at: '2023-01-01T00:00:00Z',
    updated_at: '2023-01-01T00:00:00Z',
    storage_address: '/test/path',
    signed_url: 'https://test.com/file',
    tags: ['tag1', 'tag2', 'texture|stone'],
    images: [
      {
        id: 'img1',
        image_name: 'test.jpg',
        image_url: 'https://test.com/image.jpg',
        created_at: '2023-01-01T00:00:00Z',
        updated_at: '2023-01-01T00:00:00Z',
      },
    ],
  };

  const mockConfigSelections = {};
  const mockAddTag = jest.fn();
  const mockClearTags = jest.fn();
  const mockAddAllTags = jest.fn();
  const mockTagDescriptions = { 'tag1': 'Description for tag1' };

  beforeEach(() => {
    jest.clearAllMocks();

    mockUseBlueprintContext.mockImplementation((selector) => {
      const state: BlueprintStore = {
        selectedBlueprint: mockBlueprint,
        configSelections: mockConfigSelections,
        setSelectedBlueprint: jest.fn(),
        fetchBlueprintById: jest.fn(),
        fetchBlueprintByMd5: jest.fn(),
        setConfigSelection: jest.fn(),
        clearConfigSelections: jest.fn(),
      };
      return selector(state);
    });

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
        addTag: mockAddTag,
        addAllTags: mockAddAllTags,
        removeTag: jest.fn(),
        clearTags: mockClearTags,
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

  it('renders blueprint information when blueprint is selected', () => {
    render(<BlueprintContainer />);

    expect(screen.getByText('Test Blueprint')).toBeInTheDocument();
    expect(screen.getByText(/Type:/)).toBeInTheDocument();
    expect(screen.getByText(/Last Modified:/)).toBeInTheDocument();
    // Use getAllByText and check at least one element matches
    const sizeElements = screen.getAllByText((content, node) => {
      const text = node?.textContent || '';
      return text.includes('Size:') && text.includes('1024 bytes');
    });
    expect(sizeElements.length).toBeGreaterThan(0);
  });

  it('renders "No Blueprint Selected" when no blueprint is selected', () => {
    mockUseBlueprintContext.mockImplementation((selector) => {
      const state: BlueprintStore = {
        selectedBlueprint: null,
        configSelections: mockConfigSelections,
        setSelectedBlueprint: jest.fn(),
        fetchBlueprintById: jest.fn(),
        fetchBlueprintByMd5: jest.fn(),
        setConfigSelection: jest.fn(),
        clearConfigSelections: jest.fn(),
      };
      return selector(state);
    });

    render(<BlueprintContainer />);

    expect(screen.getByText('No Blueprint Selected')).toBeInTheDocument();
  });

  it('renders blueprint tags with click handlers', () => {
    render(<BlueprintContainer />);

    const tagButtons = screen.getAllByRole('button');
    const tag1Button = tagButtons.find(button => button.textContent?.includes('tag1'));
    const tag2Button = tagButtons.find(button => button.textContent?.includes('tag2'));

    expect(tag1Button).toBeInTheDocument();
    expect(tag2Button).toBeInTheDocument();

    fireEvent.click(tag1Button!);
    expect(mockAddTag).toHaveBeenCalledWith('tag1');
  });

  it('shows tag descriptions on hover', async () => {
    render(<BlueprintContainer />);

    const tagButton = screen.getByText('tag1');
    fireEvent.mouseEnter(tagButton);

    await waitFor(() => {
      expect(screen.getByText('Description for tag1')).toBeInTheDocument();
    }, { timeout: 1000 });
  });

  it('handles copy to clipboard functionality', async () => {
    render(<BlueprintContainer />);

    const copyButton = screen.getByTitle('Copy url to clipboard');
    fireEvent.click(copyButton);

    expect(mockClipboard.writeText).toHaveBeenCalledWith('http://localhost/?md5=abc123');

    await waitFor(() => {
      expect(screen.getByTitle('url copied')).toBeInTheDocument();
    });
  });

  it('handles download functionality', () => {
    render(<BlueprintContainer />);

    const downloadLink = screen.getByText('Download');
    fireEvent.click(downloadLink);

    expect(mockDownloadFiles).toHaveBeenCalledWith(['/api/blueprints/123/download']);
  });

  it('handles swap tags functionality', () => {
    render(<BlueprintContainer />);

    const textureLink = screen.getByText('textures');
    fireEvent.click(textureLink);

    expect(mockClearTags).toHaveBeenCalled();
    expect(mockAddAllTags).toHaveBeenCalledWith(['tag1', 'tag2']);
  });

  it('renders config boxes when blueprint has parts', () => {
    const blueprintWithParts = {
      ...mockBlueprint,
      blueprint_config: {
        parts: [
          {
            name: 'part1',
            tags: { require: [{ tag: 'required_tag' }] },
          } as ConfigPart,
        ],
      },
    };

    mockUseBlueprintContext.mockImplementation((selector) => {
      const state: BlueprintStore = {
        selectedBlueprint: blueprintWithParts,
        configSelections: mockConfigSelections,
        setSelectedBlueprint: jest.fn(),
        fetchBlueprintById: jest.fn(),
        fetchBlueprintByMd5: jest.fn(),
        setConfigSelection: jest.fn(),
        clearConfigSelections: jest.fn(),
      };
      return selector(state);
    });

    render(<BlueprintContainer />);

    expect(screen.getByText('Parts Needed to Build')).toBeInTheDocument();
    expect(screen.getByTestId('config-box-part1')).toBeInTheDocument();
  });

  it('renders nested config boxes for selected parts', () => {
    const nestedBlueprint = {
      ...mockBlueprint,
      blueprint_config: {
        parts: [
          {
            name: 'parent_part',
            tags: { require: [{ tag: 'parent_tag' }] },
          } as ConfigPart,
        ],
      },
    };

    const mockConfigSelectionsWithNested = {
      parent_part: {
        ...mockBlueprint,
        blueprint_config: {
          parts: [
            {
              name: 'child_part',
              tags: { require: [{ tag: 'child_tag' }] },
            } as ConfigPart,
          ],
        },
      },
    };

    mockUseBlueprintContext.mockImplementation((selector) => {
      const state: BlueprintStore = {
        selectedBlueprint: nestedBlueprint,
        configSelections: mockConfigSelectionsWithNested,
        setSelectedBlueprint: jest.fn(),
        fetchBlueprintById: jest.fn(),
        fetchBlueprintByMd5: jest.fn(),
        setConfigSelection: jest.fn(),
        clearConfigSelections: jest.fn(),
      };
      return selector(state);
    });

    render(<BlueprintContainer />);

    expect(screen.getByText('Parts Needed for parent_part')).toBeInTheDocument();
    expect(screen.getByTestId('config-box-parent_part|child_part')).toBeInTheDocument();
  });

  it('handles part selection when configValues is provided', () => {
    const mockOnPartSelected = jest.fn();
    const configValues = { partName: 'test_part' };

    render(
      <BlueprintContainer
        configValues={configValues}
        onPartSelected={mockOnPartSelected}
      />
    );

    const selectPartLink = screen.getByText('Select This Part');
    fireEvent.click(selectPartLink);

    expect(mockOnPartSelected).toHaveBeenCalledWith('test_part', mockBlueprint);
  });

  it('shows download link when shouldShowDownloadLink returns true', () => {
    render(<BlueprintContainer />);

    expect(screen.getByText('Download')).toBeInTheDocument();
  });

  it('does not show download link when shouldShowDownloadLink returns false', () => {
    const blueprintWithoutFile = {
      ...mockBlueprint,
      file_name: '',
      blueprint_config: {
        parts: [
          {
            name: 'part1',
            tags: { require: [{ tag: 'required_tag' }] },
          } as ConfigPart,
        ],
      },
    };

    mockUseBlueprintContext.mockImplementation((selector) => {
      const state: BlueprintStore = {
        selectedBlueprint: blueprintWithoutFile,
        configSelections: mockConfigSelections,
        setSelectedBlueprint: jest.fn(),
        fetchBlueprintById: jest.fn(),
        fetchBlueprintByMd5: jest.fn(),
        setConfigSelection: jest.fn(),
        clearConfigSelections: jest.fn(),
      };
      return selector(state);
    });

    render(<BlueprintContainer />);

    expect(screen.queryByText('Download')).not.toBeInTheDocument();
  });

  it('renders blueprint images', () => {
    render(<BlueprintContainer />);

    const image = screen.getByAltText('test.jpg');
    expect(image).toBeInTheDocument();
    expect(image).toHaveAttribute('src', 'https://test.com/image.jpg');
  });

  it('filters out fulfilled parts when rendering config boxes', () => {
    const blueprintWithFulfills = {
      ...mockBlueprint,
      blueprint_config: {
        parts: [
          {
            name: 'part1',
            tags: { require: [{ tag: 'required_tag' }] },
          } as ConfigPart,
          {
            name: 'part2',
            tags: { require: [{ tag: 'required_tag2' }] },
          } as ConfigPart,
        ],
        fulfills: [{ part: 'part1' }],
      },
    };

    mockUseBlueprintContext.mockImplementation((selector) => {
      const state: BlueprintStore = {
        selectedBlueprint: blueprintWithFulfills,
        configSelections: mockConfigSelections,
        setSelectedBlueprint: jest.fn(),
        fetchBlueprintById: jest.fn(),
        fetchBlueprintByMd5: jest.fn(),
        setConfigSelection: jest.fn(),
        clearConfigSelections: jest.fn(),
      };
      return selector(state);
    });

    render(<BlueprintContainer />);

    expect(screen.queryByTestId('config-box-part1')).not.toBeInTheDocument();
    expect(screen.getByTestId('config-box-part2')).toBeInTheDocument();
  });

  it('calculates later date correctly', () => {
    const blueprintWithDifferentDates = {
      ...mockBlueprint,
      file_modified_at: '2023-01-02T00:00:00Z',
    };

    mockUseBlueprintContext.mockImplementation((selector) => {
      const state: BlueprintStore = {
        selectedBlueprint: blueprintWithDifferentDates,
        configSelections: mockConfigSelections,
        setSelectedBlueprint: jest.fn(),
        fetchBlueprintById: jest.fn(),
        fetchBlueprintByMd5: jest.fn(),
        setConfigSelection: jest.fn(),
        clearConfigSelections: jest.fn(),
      };
      return selector(state);
    });

    render(<BlueprintContainer />);

    expect(screen.getByText(/Last Modified:/)).toBeInTheDocument();
  });

  it('handles cleanup of hover timeout on unmount', () => {
    // Mock setTimeout and clearTimeout
    const mockTimeoutId = 123;
    const mockSetTimeout = jest.fn().mockReturnValue(mockTimeoutId);
    const mockClearTimeout = jest.fn();
    jest.spyOn(global, 'setTimeout').mockImplementation(mockSetTimeout);
    jest.spyOn(global, 'clearTimeout').mockImplementation(mockClearTimeout);

    const { unmount } = render(<BlueprintContainer />);

    // Trigger hover to set up timeout
    const tagButton = screen.getByText('tag1');
    fireEvent.mouseEnter(tagButton);

    // Verify setTimeout was called
    expect(mockSetTimeout).toHaveBeenCalled();

    unmount();

    // Verify clearTimeout was called during cleanup
    expect(mockClearTimeout).toHaveBeenCalledWith(mockTimeoutId);

    // Restore original implementations
    jest.restoreAllMocks();
  });
});
