import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { SearchDisplay } from '../search-display';

describe('SearchDisplay', () => {
  const mockOnClearSearch = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('renders nothing when searchTerm is null', () => {
    const { container } = render(
      <SearchDisplay
        searchTerm={null}
        onClearSearch={mockOnClearSearch}
      />
    );

    expect(container.firstChild).toBeNull();
  });

  it('renders search display when searchTerm is provided', () => {
    render(
      <SearchDisplay
        searchTerm="test search"
        onClearSearch={mockOnClearSearch}
      />
    );

    expect(screen.getByText('Search')).toBeInTheDocument();
    expect(screen.getByText('test search')).toBeInTheDocument();
    expect(screen.getByRole('button')).toBeInTheDocument();
  });

  it('calls onClearSearch when clear button is clicked', () => {
    render(
      <SearchDisplay
        searchTerm="test search"
        onClearSearch={mockOnClearSearch}
      />
    );

    const clearButton = screen.getByRole('button');
    fireEvent.click(clearButton);

    expect(mockOnClearSearch).toHaveBeenCalledTimes(1);
  });

  it('displays search term with special characters', () => {
    render(
      <SearchDisplay
        searchTerm="search with spaces & symbols"
        onClearSearch={mockOnClearSearch}
      />
    );

    expect(screen.getByText('search with spaces & symbols')).toBeInTheDocument();
  });

  it('renders correct structure with header and list', () => {
    render(
      <SearchDisplay
        searchTerm="test"
        onClearSearch={mockOnClearSearch}
      />
    );

    const header = screen.getByText('Search');
    const listItem = screen.getByText('test');

    expect(header).toHaveClass('selectedTagsContainer__header');
    expect(listItem.closest('ul')).toBeInTheDocument();
  });
});
