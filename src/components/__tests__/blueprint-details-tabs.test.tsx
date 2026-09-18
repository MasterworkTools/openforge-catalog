import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import BlueprintDetailsTabs from '../blueprint-details-tabs';
import { createMockBlueprint } from '@/test-utils';
import { DocumentationService } from '@/services/documentation-service';

// Mock the documentation service
jest.mock('@/services/documentation-service', () => ({
  DocumentationService: {
    getBlueprintAllDocumentation: jest.fn()
  }
}));

// Mock the documentation components
jest.mock('../blueprint/documentation-tab', () => {
  return function MockDocumentationTab() {
    return <div data-testid="documentation-tab">Documentation Tab</div>;
  };
});

jest.mock('../blueprint/changelog-section', () => {
  return function MockChangelogSection() {
    return <div data-testid="changelog-section">Changelog Section</div>;
  };
});

describe('BlueprintDetailsTabs', () => {
  const mockBlueprint = createMockBlueprint();

  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('renders details tab by default', () => {
    render(
      <BlueprintDetailsTabs blueprint={mockBlueprint}>
        <div data-testid="details-content">Details Content</div>
      </BlueprintDetailsTabs>
    );

    expect(screen.getByText('Details')).toBeInTheDocument();
    expect(screen.getByTestId('details-content')).toBeInTheDocument();
    expect(screen.queryByText('Documentation')).not.toBeInTheDocument();
  });

  it('shows documentation tab when documentation exists', async () => {
    (DocumentationService.getBlueprintAllDocumentation as jest.Mock).mockResolvedValue({
      blueprint_documentation: [
        {
          id: '1',
          blueprint_id: 'bp-1',
          document: 'Test documentation',
          document_type: 'instructions',
          created_at: '2023-01-01T00:00:00Z',
          updated_at: '2023-01-01T00:00:00Z'
        }
      ],
      tag_documentation: {},
      changelog_history: { changelogs: [], has_more: false, total_count: 0 }
    });

    render(
      <BlueprintDetailsTabs blueprint={mockBlueprint}>
        <div data-testid="details-content">Details Content</div>
      </BlueprintDetailsTabs>
    );

    // Wait for documentation to load
    await screen.findByText('Documentation');

    expect(screen.getByText('Documentation')).toBeInTheDocument();
    expect(screen.getByTestId('details-content')).toBeInTheDocument();
  });

  it('switches between tabs when clicked', async () => {
    (DocumentationService.getBlueprintAllDocumentation as jest.Mock).mockResolvedValue({
      blueprint_documentation: [
        {
          id: '1',
          blueprint_id: 'bp-1',
          document: 'Test documentation',
          document_type: 'instructions',
          created_at: '2023-01-01T00:00:00Z',
          updated_at: '2023-01-01T00:00:00Z'
        }
      ],
      tag_documentation: {},
      changelog_history: { changelogs: [], has_more: false, total_count: 0 }
    });

    render(
      <BlueprintDetailsTabs blueprint={mockBlueprint}>
        <div data-testid="details-content">Details Content</div>
      </BlueprintDetailsTabs>
    );

    // Wait for documentation to load
    await screen.findByText('Documentation');

    // Initially details content should be visible and documentation tab should not
    expect(screen.getByTestId('details-content')).toBeInTheDocument();

    // The documentation tab should be rendered but hidden
    expect(screen.getByTestId('documentation-tab')).toBeInTheDocument();

    // Click documentation tab
    fireEvent.click(screen.getByText('Documentation'));

    // Wait for the state to update and check that details is hidden
    await waitFor(() => {
      const detailsContent = screen.getByTestId('details-content');
      expect(detailsContent.parentElement).toHaveStyle({ display: 'none' });
    });

    // Now documentation tab should be visible
    expect(screen.getByTestId('documentation-tab')).toBeInTheDocument();
  });

  it('does not show documentation tab when no documentation exists', () => {
    (DocumentationService.getBlueprintAllDocumentation as jest.Mock).mockResolvedValue(null);

    render(
      <BlueprintDetailsTabs blueprint={mockBlueprint}>
        <div data-testid="details-content">Details Content</div>
      </BlueprintDetailsTabs>
    );

    expect(screen.getByText('Details')).toBeInTheDocument();
    expect(screen.queryByText('Documentation')).not.toBeInTheDocument();
    expect(screen.getByTestId('details-content')).toBeInTheDocument();
  });

  it('handles API errors gracefully', () => {
    (DocumentationService.getBlueprintAllDocumentation as jest.Mock).mockRejectedValue(new Error('API Error'));

    render(
      <BlueprintDetailsTabs blueprint={mockBlueprint}>
        <div data-testid="details-content">Details Content</div>
      </BlueprintDetailsTabs>
    );

    expect(screen.getByText('Details')).toBeInTheDocument();
    expect(screen.queryByText('Documentation')).not.toBeInTheDocument();
    expect(screen.getByTestId('details-content')).toBeInTheDocument();
  });
});
