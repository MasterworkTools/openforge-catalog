import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { PaginationControls } from '../pagination-controls';
import { createMockPaging } from '@/test-utils';

describe('PaginationControls', () => {
  const mockOnPrevious = jest.fn();
  const mockOnNext = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('renders pagination controls with all elements', () => {
    const paging = createMockPaging();

    render(
      <PaginationControls
        paging={paging}
        startCount={11}
        endCount={20}
        totalCount={100}
        onPrevious={mockOnPrevious}
        onNext={mockOnNext}
      />
    );

    const countElements = screen.getAllByText((content, element) =>
      element?.textContent?.includes('11 - 20 of 100 that match your tags') || false
    );
    expect(countElements.length).toBeGreaterThan(0);
    expect(screen.getByText('Previous Page')).toBeInTheDocument();
    expect(screen.getByText('Next Page')).toBeInTheDocument();
  });

  it('calls onPrevious when Previous Page button is clicked', () => {
    const paging = createMockPaging();

    render(
      <PaginationControls
        paging={paging}
        startCount={11}
        endCount={20}
        totalCount={100}
        onPrevious={mockOnPrevious}
        onNext={mockOnNext}
      />
    );

    fireEvent.click(screen.getByText('Previous Page'));
    expect(mockOnPrevious).toHaveBeenCalledTimes(1);
  });

  it('calls onNext when Next Page button is clicked', () => {
    const paging = createMockPaging();

    render(
      <PaginationControls
        paging={paging}
        startCount={1}
        endCount={10}
        totalCount={100}
        onPrevious={mockOnPrevious}
        onNext={mockOnNext}
      />
    );

    fireEvent.click(screen.getByText('Next Page'));
    expect(mockOnNext).toHaveBeenCalledTimes(1);
  });

  it('hides Previous Page button when no previous token', () => {
    const paging = createMockPaging({ previous_token: undefined });

    render(
      <PaginationControls
        paging={paging}
        startCount={11}
        endCount={20}
        totalCount={100}
        onPrevious={mockOnPrevious}
        onNext={mockOnNext}
      />
    );

    expect(screen.queryByText('Previous Page')).not.toBeInTheDocument();
    expect(screen.getByText('Next Page')).toBeInTheDocument();
  });

  it('hides Previous Page button when startCount is 1', () => {
    const paging = createMockPaging();

    render(
      <PaginationControls
        paging={paging}
        startCount={1}
        endCount={10}
        totalCount={100}
        onPrevious={mockOnPrevious}
        onNext={mockOnNext}
      />
    );

    expect(screen.queryByText('Previous Page')).not.toBeInTheDocument();
    expect(screen.getByText('Next Page')).toBeInTheDocument();
  });

  it('hides Next Page button when no next token', () => {
    const paging = createMockPaging({ next_token: undefined });

    render(
      <PaginationControls
        paging={paging}
        startCount={11}
        endCount={20}
        totalCount={100}
        onPrevious={mockOnPrevious}
        onNext={mockOnNext}
      />
    );

    expect(screen.getByText('Previous Page')).toBeInTheDocument();
    expect(screen.queryByText('Next Page')).not.toBeInTheDocument();
  });

  it('hides Next Page button when endCount equals total_count', () => {
    const paging = createMockPaging();

    render(
      <PaginationControls
        paging={paging}
        startCount={91}
        endCount={100}
        totalCount={100}
        onPrevious={mockOnPrevious}
        onNext={mockOnNext}
      />
    );

    expect(screen.getByText('Previous Page')).toBeInTheDocument();
    expect(screen.queryByText('Next Page')).not.toBeInTheDocument();
  });

  it('handles null paging gracefully', () => {
    render(
      <PaginationControls
        paging={null}
        startCount={1}
        endCount={10}
        totalCount={0}
        onPrevious={mockOnPrevious}
        onNext={mockOnNext}
      />
    );

    const countElements = screen.getAllByText((content, element) =>
      element?.textContent?.includes('1 - 10 of 0 that match your tags') || false
    );
    expect(countElements.length).toBeGreaterThan(0);
    expect(screen.queryByText('Previous Page')).not.toBeInTheDocument();
    expect(screen.queryByText('Next Page')).not.toBeInTheDocument();
  });

  it('displays correct count information', () => {
    const paging = createMockPaging();

    render(
      <PaginationControls
        paging={paging}
        startCount={5}
        endCount={15}
        totalCount={50}
        onPrevious={mockOnPrevious}
        onNext={mockOnNext}
      />
    );

    const countElements = screen.getAllByText((content, element) =>
      element?.textContent?.includes('5 - 15 of 50 that match your tags') || false
    );
    expect(countElements.length).toBeGreaterThan(0);
  });
});
