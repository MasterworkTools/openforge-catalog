import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import DocumentationEditor from '../documentation-editor';

// Mock the child components
jest.mock('../admin-blueprint-picker', () => {
  return function MockAdminBlueprintPicker({ isOpen, onSelect, onClose }: { isOpen: boolean; onSelect: (blueprint: { id: string; blueprint_name: string }) => void; onClose: () => void }) {
    if (!isOpen) return null;
    return (
      <div data-testid="blueprint-picker">
        <button onClick={() => onSelect({ id: 'test-blueprint', blueprint_name: 'Test Blueprint' })}>
          Select Test Blueprint
        </button>
        <button onClick={onClose}>Close</button>
      </div>
    );
  };
});

jest.mock('../admin-tag-picker', () => {
  return function MockAdminTagPicker({ isOpen, onSelect, onClose }: { isOpen: boolean; onSelect: (tag: string[]) => void; onClose: () => void }) {
    if (!isOpen) return null;
    return (
      <div data-testid="tag-picker">
        <button onClick={() => onSelect(['texture', 'dungeon_stone'])}>
          Select Test Tag
        </button>
        <button onClick={onClose}>Close</button>
      </div>
    );
  };
});

jest.mock('../markdown-editor', () => {
  return function MockMarkdownEditor({ target }: { target: { type: string; blueprint?: { id: string; blueprint_name: string }; tag?: string[] } }) {
    return (
      <div data-testid="markdown-editor">
        <span>Editing: {target.type === 'blueprint' ? target.blueprint?.blueprint_name : target.tag?.join(': ')}</span>
      </div>
    );
  };
});

describe('DocumentationEditor', () => {
  beforeEach(() => {
    // Clear all mocks before each test
    jest.clearAllMocks();
  });

  it('renders with blueprint as default target type', () => {
    render(<DocumentationEditor />);

    expect(screen.getByText('Documentation Editor')).toBeInTheDocument();
    expect(screen.getByLabelText('Blueprint')).toBeChecked();
    expect(screen.getByLabelText('Tag')).not.toBeChecked();
    expect(screen.getByText('Select Blueprint')).toBeInTheDocument();
  });

  it('switches to tag target type when tag radio is clicked', () => {
    render(<DocumentationEditor />);

    const tagRadio = screen.getByLabelText('Tag');
    fireEvent.click(tagRadio);

    expect(tagRadio).toBeChecked();
    expect(screen.getByLabelText('Blueprint')).not.toBeChecked();
    expect(screen.getByText('Select Tag')).toBeInTheDocument();
  });

  it('shows blueprint picker when blueprint selector is clicked', () => {
    render(<DocumentationEditor />);

    const blueprintButton = screen.getByText('Select Blueprint');
    fireEvent.click(blueprintButton);

    expect(screen.getByTestId('blueprint-picker')).toBeInTheDocument();
  });

  it('shows tag picker when tag selector is clicked', () => {
    render(<DocumentationEditor />);

    // Switch to tag mode first
    fireEvent.click(screen.getByLabelText('Tag'));

    const tagButton = screen.getByText('Select Tag');
    fireEvent.click(tagButton);

    expect(screen.getByTestId('tag-picker')).toBeInTheDocument();
  });

  it('displays selected blueprint and shows markdown editor', async () => {
    render(<DocumentationEditor />);

    // Open blueprint picker and select a blueprint
    fireEvent.click(screen.getByText('Select Blueprint'));
    fireEvent.click(screen.getByText('Select Test Blueprint'));

    await waitFor(() => {
      expect(screen.getByText('Test Blueprint')).toBeInTheDocument();
      expect(screen.getByTestId('markdown-editor')).toBeInTheDocument();
      expect(screen.getByText('Editing: Test Blueprint')).toBeInTheDocument();
    });
  });

  it('displays selected tag and shows markdown editor', async () => {
    render(<DocumentationEditor />);

    // Switch to tag mode
    fireEvent.click(screen.getByLabelText('Tag'));

    // Open tag picker and select a tag
    fireEvent.click(screen.getByText('Select Tag'));
    fireEvent.click(screen.getByText('Select Test Tag'));

    await waitFor(() => {
      expect(screen.getByText('texture: dungeon_stone')).toBeInTheDocument();
      expect(screen.getByTestId('markdown-editor')).toBeInTheDocument();
      expect(screen.getByText('Editing: texture: dungeon_stone')).toBeInTheDocument();
    });
  });

  it('clears selection when clear button is clicked', async () => {
    render(<DocumentationEditor />);

    // Select a blueprint first
    fireEvent.click(screen.getByText('Select Blueprint'));
    fireEvent.click(screen.getByText('Select Test Blueprint'));

    await waitFor(() => {
      expect(screen.getByText('Test Blueprint')).toBeInTheDocument();
    });

    // Clear the selection
    fireEvent.click(screen.getByText('Clear'));

    await waitFor(() => {
      expect(screen.getByText('Select Blueprint')).toBeInTheDocument();
      expect(screen.queryByTestId('markdown-editor')).not.toBeInTheDocument();
    });
  });

  it('resets selection when switching target types', async () => {
    render(<DocumentationEditor />);

    // Select a blueprint first
    fireEvent.click(screen.getByText('Select Blueprint'));
    fireEvent.click(screen.getByText('Select Test Blueprint'));

    await waitFor(() => {
      expect(screen.getByText('Test Blueprint')).toBeInTheDocument();
    });

    // Switch to tag mode
    fireEvent.click(screen.getByLabelText('Tag'));

    await waitFor(() => {
      expect(screen.getByText('Select Tag')).toBeInTheDocument();
      expect(screen.queryByTestId('markdown-editor')).not.toBeInTheDocument();
    });
  });
});
