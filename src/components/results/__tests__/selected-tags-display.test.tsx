import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { SelectedTagsDisplay } from '../selected-tags-display';
import { createMockConfigTags, mockClipboard } from '@/test-utils';

// Mock clipboard API
Object.assign(navigator, {
  clipboard: mockClipboard,
});

describe('SelectedTagsDisplay', () => {
  const mockOnRemoveTag = jest.fn();
  const mockOnClearSearch = jest.fn();
  const mockOnCreateDeepLink = jest.fn();
  const mockOnCopyToClipboard = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('renders nothing when no tags or search term', () => {
    const { container } = render(
      <SelectedTagsDisplay
        selectedTags={[]}
        denyTags={[]}
        searchTerm={null}
        configValues={null}
        isTagRemovable={() => true}
        onRemoveTag={mockOnRemoveTag}
        onClearSearch={mockOnClearSearch}
        onCreateDeepLink={mockOnCreateDeepLink}
        onCopyToClipboard={mockOnCopyToClipboard}
        copied={false}
      />
    );

    expect(container.firstChild).toBeNull();
  });

  it('renders selected tags section', () => {
    render(
      <SelectedTagsDisplay
        selectedTags={['tag1', 'tag2']}
        denyTags={[]}
        searchTerm={null}
        configValues={null}
        isTagRemovable={() => true}
        onRemoveTag={mockOnRemoveTag}
        onClearSearch={mockOnClearSearch}
        onCreateDeepLink={mockOnCreateDeepLink}
        onCopyToClipboard={mockOnCopyToClipboard}
        copied={false}
      />
    );

    const selectedTagsElements = screen.getAllByText((content, element) =>
      element?.textContent?.includes('Selected Tags') || false
    );
    expect(selectedTagsElements.length).toBeGreaterThan(0);
    expect(screen.getByText('tag1')).toBeInTheDocument();
    expect(screen.getByText('tag2')).toBeInTheDocument();
  });

  it('renders search display when searchTerm is provided', () => {
    render(
      <SelectedTagsDisplay
        selectedTags={[]}
        denyTags={[]}
        searchTerm="test search"
        configValues={null}
        isTagRemovable={() => true}
        onRemoveTag={mockOnRemoveTag}
        onClearSearch={mockOnClearSearch}
        onCreateDeepLink={mockOnCreateDeepLink}
        onCopyToClipboard={mockOnCopyToClipboard}
        copied={false}
      />
    );

    expect(screen.getByText('Search')).toBeInTheDocument();
    expect(screen.getByText('test search')).toBeInTheDocument();
  });

  it('renders denied tags section', () => {
    render(
      <SelectedTagsDisplay
        selectedTags={[]}
        denyTags={['denied1', 'denied2']}
        searchTerm={null}
        configValues={null}
        isTagRemovable={() => true}
        onRemoveTag={mockOnRemoveTag}
        onClearSearch={mockOnClearSearch}
        onCreateDeepLink={mockOnCreateDeepLink}
        onCopyToClipboard={mockOnCopyToClipboard}
        copied={false}
      />
    );

    expect(screen.getByText('Denied Tags')).toBeInTheDocument();
    expect(screen.getByText('denied1')).toBeInTheDocument();
    expect(screen.getByText('denied2')).toBeInTheDocument();
  });

  it('calls onRemoveTag when tag remove button is clicked', () => {
    render(
      <SelectedTagsDisplay
        selectedTags={['removable-tag']}
        denyTags={[]}
        searchTerm={null}
        configValues={null}
        isTagRemovable={() => true}
        onRemoveTag={mockOnRemoveTag}
        onClearSearch={mockOnClearSearch}
        onCreateDeepLink={mockOnCreateDeepLink}
        onCopyToClipboard={mockOnCopyToClipboard}
        copied={false}
      />
    );

    const removeButton = screen.getByText('removable-tag').parentElement?.querySelector('button');
    if (removeButton) fireEvent.click(removeButton);

    expect(mockOnRemoveTag).toHaveBeenCalledWith('removable-tag');
  });

  it('calls onClearSearch when search clear button is clicked', () => {
    render(
      <SelectedTagsDisplay
        selectedTags={[]}
        denyTags={[]}
        searchTerm="test search"
        configValues={null}
        isTagRemovable={() => true}
        onRemoveTag={mockOnRemoveTag}
        onClearSearch={mockOnClearSearch}
        onCreateDeepLink={mockOnCreateDeepLink}
        onCopyToClipboard={mockOnCopyToClipboard}
        copied={false}
      />
    );

    const clearButton = screen.getByText('test search').parentElement?.querySelector('button');
    if (clearButton) fireEvent.click(clearButton);

    expect(mockOnClearSearch).toHaveBeenCalledTimes(1);
  });

  it('does not show remove button for non-removable tags', () => {
    render(
      <SelectedTagsDisplay
        selectedTags={['non-removable']}
        denyTags={[]}
        searchTerm={null}
        configValues={null}
        isTagRemovable={() => false}
        onRemoveTag={mockOnRemoveTag}
        onClearSearch={mockOnClearSearch}
        onCreateDeepLink={mockOnCreateDeepLink}
        onCopyToClipboard={mockOnCopyToClipboard}
        copied={false}
      />
    );

    expect(screen.getByText('non-removable')).toBeInTheDocument();
    const removeButton = screen.getByText('non-removable').parentElement?.querySelector('button');
    expect(removeButton).not.toBeInTheDocument();
  });

  it('shows deeplink and copy button when no configValues', () => {
    mockOnCreateDeepLink.mockReturnValue('tag=tag1&tag=tag2');

    render(
      <SelectedTagsDisplay
        selectedTags={['tag1', 'tag2']}
        denyTags={[]}
        searchTerm={null}
        configValues={null}
        isTagRemovable={() => true}
        onRemoveTag={mockOnRemoveTag}
        onClearSearch={mockOnClearSearch}
        onCreateDeepLink={mockOnCreateDeepLink}
        onCopyToClipboard={mockOnCopyToClipboard}
        copied={false}
      />
    );

    expect(screen.getByText('deeplink')).toBeInTheDocument();
    expect(screen.getByTitle('Copy url to clipboard')).toBeInTheDocument();
  });

  it('shows deeplink and copy button with only deny tags', () => {
    mockOnCreateDeepLink.mockReturnValue('deny=denied1&deny=denied2');

    render(
      <SelectedTagsDisplay
        selectedTags={[]}
        denyTags={['denied1', 'denied2']}
        searchTerm={null}
        configValues={null}
        isTagRemovable={() => true}
        onRemoveTag={mockOnRemoveTag}
        onClearSearch={mockOnClearSearch}
        onCreateDeepLink={mockOnCreateDeepLink}
        onCopyToClipboard={mockOnCopyToClipboard}
        copied={false}
      />
    );

    expect(screen.getByText('deeplink')).toBeInTheDocument();
    expect(screen.getByTitle('Copy url to clipboard')).toBeInTheDocument();
    expect(screen.getByText('Denied Tags')).toBeInTheDocument();
    expect(screen.getByText('denied1')).toBeInTheDocument();
    expect(screen.getByText('denied2')).toBeInTheDocument();
  });

  it('does not show deeplink and copy button when configValues is provided', () => {
    const configValues = createMockConfigTags();

    render(
      <SelectedTagsDisplay
        selectedTags={['tag1', 'tag2']}
        denyTags={[]}
        searchTerm={null}
        configValues={configValues}
        isTagRemovable={() => true}
        onRemoveTag={mockOnRemoveTag}
        onClearSearch={mockOnClearSearch}
        onCreateDeepLink={mockOnCreateDeepLink}
        onCopyToClipboard={mockOnCopyToClipboard}
        copied={false}
      />
    );

    expect(screen.queryByText('deeplink')).not.toBeInTheDocument();
    expect(screen.queryByTitle('Copy url to clipboard')).not.toBeInTheDocument();
  });

  it('calls onCopyToClipboard when copy button is clicked', () => {
    mockOnCreateDeepLink.mockReturnValue('tag=tag1&tag=tag2');

    render(
      <SelectedTagsDisplay
        selectedTags={['tag1', 'tag2']}
        denyTags={[]}
        searchTerm={null}
        configValues={null}
        isTagRemovable={() => true}
        onRemoveTag={mockOnRemoveTag}
        onClearSearch={mockOnClearSearch}
        onCreateDeepLink={mockOnCreateDeepLink}
        onCopyToClipboard={mockOnCopyToClipboard}
        copied={false}
      />
    );

    const copyButton = screen.getByTitle('Copy url to clipboard');
    fireEvent.click(copyButton);

    expect(mockOnCopyToClipboard).toHaveBeenCalledWith('tag=tag1&tag=tag2');
  });

  it('shows copied state in copy button title', () => {
    mockOnCreateDeepLink.mockReturnValue('tag=tag1&tag=tag2');

    render(
      <SelectedTagsDisplay
        selectedTags={['tag1', 'tag2']}
        denyTags={[]}
        searchTerm={null}
        configValues={null}
        isTagRemovable={() => true}
        onRemoveTag={mockOnRemoveTag}
        onClearSearch={mockOnClearSearch}
        onCreateDeepLink={mockOnCreateDeepLink}
        onCopyToClipboard={mockOnCopyToClipboard}
        copied={true}
      />
    );

    expect(screen.getByTitle('url copied')).toBeInTheDocument();
  });

  it('removes duplicate tags from display', () => {
    render(
      <SelectedTagsDisplay
        selectedTags={['tag1', 'tag1', 'tag2']}
        denyTags={[]}
        searchTerm={null}
        configValues={null}
        isTagRemovable={() => true}
        onRemoveTag={mockOnRemoveTag}
        onClearSearch={mockOnClearSearch}
        onCreateDeepLink={mockOnCreateDeepLink}
        onCopyToClipboard={mockOnCopyToClipboard}
        copied={false}
      />
    );

    const tag1Elements = screen.getAllByText('tag1');
    expect(tag1Elements).toHaveLength(1); // Should only show one instance
    expect(screen.getByText('tag2')).toBeInTheDocument();
  });

  it('renders denied tags with red color', () => {
    render(
      <SelectedTagsDisplay
        selectedTags={[]}
        denyTags={['denied-tag']}
        searchTerm={null}
        configValues={null}
        isTagRemovable={() => true}
        onRemoveTag={mockOnRemoveTag}
        onClearSearch={mockOnClearSearch}
        onCreateDeepLink={mockOnCreateDeepLink}
        onCopyToClipboard={mockOnCopyToClipboard}
        copied={false}
      />
    );

    const deniedTag = screen.getByText('denied-tag');
    expect(deniedTag).toHaveClass('text-red-600');
  });
});
