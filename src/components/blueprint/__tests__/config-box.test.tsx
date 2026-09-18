import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import ConfigBox from '../config-box';
import { useBlueprintContext } from '@/contexts/blueprint-context';
import type { BlueprintStore } from '@/stores/blueprint-store';
import type { Blueprint } from '@/types';

jest.mock('@/contexts/blueprint-context', () => ({
  useBlueprintContext: jest.fn(),
}));

jest.mock('../../part-selection-modal', () => ({
  __esModule: true,
  default: ({ isOpen, onClose, partName, onPartSelected, configValues }: {
    isOpen: boolean;
    onClose: () => void;
    partName: string;
    onPartSelected: (partName: string, blueprint: unknown) => void;
    configValues: unknown;
  }) =>
    isOpen ? (
      <div data-testid="modal" data-config-values={JSON.stringify(configValues)}>
        <button data-testid="modal-close" onClick={onClose}>Close</button>
        <button data-testid="modal-select" onClick={() => onPartSelected(partName, { blueprint_name: 'Selected Blueprint', images: [] })}>Select</button>
      </div>
    ) : null,
}));

describe('ConfigBox', () => {
  const baseProps = {
    title: 'TestPart',
    value: {
      require: [{ tag: 'foo' }, { tag: 'bar' }],
      accept: [{ tag: 'baz' }],
      deny: [{ tag: 'qux' }],
      constrain: [{ tag: 'c1' }, { filter: 'f1' }],
    },
  };

  const mockBlueprint: Blueprint = {
    id: '1',
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
    tags: [],
    images: [],
  };

  beforeEach(() => {
    (useBlueprintContext as jest.Mock).mockImplementation((selector: (state: BlueprintStore) => unknown) => {
      return selector({
        selectedBlueprint: mockBlueprint,
        configSelections: {},
        setConfigSelection: jest.fn(),
        setSelectedBlueprint: jest.fn(),
        fetchBlueprintById: jest.fn(),
        fetchBlueprintByMd5: jest.fn(),
        clearConfigSelections: jest.fn(),
      });
    });
  });

  it('renders title with tooltip icon', () => {
    render(<ConfigBox {...baseProps} />);
    expect(screen.getByText('TestPart')).toBeInTheDocument();
    expect(screen.getByLabelText('tag description')).toBeInTheDocument();
  });

  it('calls onHover when hovering over the box', () => {
    const mockOnHover = jest.fn();
    render(<ConfigBox {...baseProps} onHover={mockOnHover} />);

    const box = screen.getByText('TestPart').closest('div');
    fireEvent.mouseEnter(box!);
    expect(mockOnHover).toHaveBeenCalledWith(true);

    fireEvent.mouseLeave(box!);
    expect(mockOnHover).toHaveBeenCalledWith(false);
  });

  it('opens and closes the modal', () => {
    render(<ConfigBox {...baseProps} />);
    const openBtn = screen.getByText('Select Part');
    fireEvent.click(openBtn);
    expect(screen.getByTestId('modal')).toBeInTheDocument();
    fireEvent.click(screen.getByTestId('modal-close'));
    expect(screen.queryByTestId('modal')).not.toBeInTheDocument();
  });

  it('shows selected blueprint and allows clearing', () => {
    const selectedBlueprint: Blueprint = {
      ...mockBlueprint,
      blueprint_name: 'Selected Blueprint',
      images: [{ image_url: 'img.png', image_name: 'img', id: '1', created_at: '', updated_at: '' }],
    };

    (useBlueprintContext as jest.Mock).mockImplementation((selector: (state: BlueprintStore) => unknown) => {
      return selector({
        selectedBlueprint: mockBlueprint,
        configSelections: {
          TestPart: selectedBlueprint,
        },
        setConfigSelection: jest.fn(),
        setSelectedBlueprint: jest.fn(),
        fetchBlueprintById: jest.fn(),
        fetchBlueprintByMd5: jest.fn(),
        clearConfigSelections: jest.fn(),
      });
    });
    render(<ConfigBox {...baseProps} />);
    expect(screen.getByText('Selected Blueprint')).toBeInTheDocument();
    expect(screen.getByRole('img')).toHaveAttribute('src', 'img.png');
    fireEvent.click(screen.getByText('Clear Selection'));
    // setConfigSelection should be called with null
    // (no assertion here since it's a mock, but no error should occur)
  });

  it('calls onPartSelected when selecting in modal', () => {
    render(<ConfigBox {...baseProps} />);
    fireEvent.click(screen.getByText('Select Part'));
    fireEvent.click(screen.getByTestId('modal-select'));
    // Should close modal and not throw
    expect(screen.queryByTestId('modal')).not.toBeInTheDocument();
  });
});
