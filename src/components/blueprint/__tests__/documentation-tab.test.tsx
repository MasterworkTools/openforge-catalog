import React from 'react';
import { render, screen } from '@testing-library/react';
import DocumentationTab from '../documentation-tab';
import { BlueprintDocumentation, TagDocumentation } from '@/types';

// Mock react-markdown
jest.mock('react-markdown', () => {
  return function MockReactMarkdown({ children }: { children: string }) {
    return <div data-testid="markdown-content">{children}</div>;
  };
});

describe('DocumentationTab', () => {
  const mockBlueprintDocumentation: BlueprintDocumentation[] = [
    {
      id: '1',
      blueprint_id: 'bp-1',
      document: '# Test Documentation\n\nThis is test content.',
      document_type: 'instructions',
      created_at: '2023-01-01T00:00:00Z',
      updated_at: '2023-01-01T00:00:00Z',
      is_live: true
    }
  ];

  const mockTagDocumentation: Record<string, TagDocumentation[]> = {
    'texture|dungeon_stone': [
      {
        id: '2',
        tag: ['texture', 'dungeon_stone'],
        document: 'This is dungeon stone texture documentation.',
        document_type: 'instructions',
        created_at: '2023-01-01T00:00:00Z',
        updated_at: '2023-01-01T00:00:00Z',
        is_live: true
      }
    ]
  };

  it('renders blueprint documentation', () => {
    render(
      <DocumentationTab
        blueprintDocumentation={mockBlueprintDocumentation}
        tagDocumentation={{}}
      />
    );

    expect(screen.getByText('Documentation')).toBeInTheDocument();
    expect(screen.getByTestId('markdown-content')).toBeInTheDocument();
  });

  it('renders tag documentation', () => {
    render(
      <DocumentationTab
        blueprintDocumentation={[]}
        tagDocumentation={mockTagDocumentation}
      />
    );

    expect(screen.getByText('texture: dungeon_stone')).toBeInTheDocument();
    expect(screen.getByText('This is dungeon stone texture documentation.')).toBeInTheDocument();
  });

  it('renders both blueprint and tag documentation', () => {
    render(
      <DocumentationTab
        blueprintDocumentation={mockBlueprintDocumentation}
        tagDocumentation={mockTagDocumentation}
      />
    );

    expect(screen.getByText('Documentation')).toBeInTheDocument();
    expect(screen.getByText('texture: dungeon_stone')).toBeInTheDocument();
  });

  it('shows no documentation message when empty', () => {
    render(
      <DocumentationTab
        blueprintDocumentation={[]}
        tagDocumentation={{}}
      />
    );

    expect(screen.getByText('No documentation available for this blueprint.')).toBeInTheDocument();
  });

  it('filters out changelog documentation', () => {
    const docsWithChangelog: BlueprintDocumentation[] = [
      {
        id: '1',
        blueprint_id: 'bp-1',
        document: 'This is instructions.',
        document_type: 'instructions',
        created_at: '2023-01-01T00:00:00Z',
        updated_at: '2023-01-01T00:00:00Z',
        is_live: true
      },
      {
        id: '2',
        blueprint_id: 'bp-1',
        document: 'This is changelog.',
        document_type: 'changelog',
        created_at: '2023-01-01T00:00:00Z',
        updated_at: '2023-01-01T00:00:00Z',
        is_live: true
      }
    ];

    render(
      <DocumentationTab
        blueprintDocumentation={docsWithChangelog}
        tagDocumentation={{}}
      />
    );

    expect(screen.getByText('Documentation')).toBeInTheDocument();
    expect(screen.getByText('This is instructions.')).toBeInTheDocument();
    expect(screen.queryByText('This is changelog.')).not.toBeInTheDocument();
  });
});
