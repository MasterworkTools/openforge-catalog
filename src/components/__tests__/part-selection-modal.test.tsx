import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import PartSelectionModal from '../part-selection-modal';

jest.mock('@/contexts/blueprint-context', () => ({
  BlueprintProvider: ({ children }: { children: React.ReactNode }) => <div data-testid="blueprint-provider">{children}</div>,
}));
jest.mock('@/contexts/tag-context', () => ({
  TagProvider: ({ children }: { children: React.ReactNode }) => <div data-testid="tag-provider">{children}</div>,
}));
jest.mock('../tag-container', () => {
  const TagContainer = () => <div data-testid="tag-container">TagContainer</div>;
  TagContainer.displayName = 'TagContainer';
  return TagContainer;
});
jest.mock('../results-container', () => {
  const ResultsContainer = () => <div data-testid="results-container">ResultsContainer</div>;
  ResultsContainer.displayName = 'ResultsContainer';
  return ResultsContainer;
});
jest.mock('../blueprint-container', () => ({
  __esModule: true,
  default: ({ onPartSelected }: { onPartSelected?: (partName: string, blueprint: unknown) => void }) => (
    <div data-testid="blueprint-container">
      BlueprintContainer
      <button data-testid="select-part" onClick={() => onPartSelected && onPartSelected('partName', { blueprint_name: 'BP', images: [] })}>Select</button>
    </div>
  ),
}));

describe('PartSelectionModal', () => {
  const baseProps = {
    isOpen: true,
    onClose: jest.fn(),
    partName: 'TestPart',
    configValues: { require: [], deny: [], accept: [], constrain: [] },
    onPartSelected: jest.fn(),
    tagsFromOtherSelections: ['tag1', 'tag2'],
  };

  afterEach(() => {
    jest.clearAllMocks();
  });

  it('renders modal with header and children when open', () => {
    render(<PartSelectionModal {...baseProps} />);
    expect(screen.getByText('Part Selection For Blueprint: TestPart')).toBeInTheDocument();
    expect(screen.getByTestId('tag-provider')).toBeInTheDocument();
    expect(screen.getByTestId('blueprint-provider')).toBeInTheDocument();
    expect(screen.getByTestId('tag-container')).toBeInTheDocument();
    expect(screen.getByTestId('results-container')).toBeInTheDocument();
    expect(screen.getByTestId('blueprint-container')).toBeInTheDocument();
  });

  it('does not render when isOpen is false', () => {
    render(<PartSelectionModal {...baseProps} isOpen={false} />);
    expect(screen.queryByText('Part Selection For Blueprint: TestPart')).not.toBeInTheDocument();
  });

  it('calls onClose when close button is clicked', () => {
    render(<PartSelectionModal {...baseProps} />);
    fireEvent.click(screen.getAllByRole('button')[0]);
    expect(baseProps.onClose).toHaveBeenCalled();
  });

  it('calls onPartSelected when selecting a part', () => {
    render(<PartSelectionModal {...baseProps} />);
    fireEvent.click(screen.getByTestId('select-part'));
    expect(baseProps.onPartSelected).toHaveBeenCalledWith('partName', expect.objectContaining({ blueprint_name: 'BP' }));
  });
});
