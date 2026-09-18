import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { BlueprintList } from '../blueprint-list';
import { createMockBlueprint } from '@/test-utils';

describe('BlueprintList', () => {
  const mockOnSelectBlueprint = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('renders empty list when no blueprints', () => {
    render(
      <BlueprintList
        blueprints={[]}
        selectedBlueprint={null}
        onSelectBlueprint={mockOnSelectBlueprint}
      />
    );

    const list = screen.getByRole('list');
    expect(list).toBeInTheDocument();
    expect(list.children).toHaveLength(0);
  });

  it('renders list of blueprints', () => {
    const blueprints = [
      createMockBlueprint({ id: '1', blueprint_name: 'Blueprint 1' }),
      createMockBlueprint({ id: '2', blueprint_name: 'Blueprint 2' }),
    ];

    render(
      <BlueprintList
        blueprints={blueprints}
        selectedBlueprint={null}
        onSelectBlueprint={mockOnSelectBlueprint}
      />
    );

    expect(screen.getByText('Blueprint 1')).toBeInTheDocument();
    expect(screen.getByText('Blueprint 2')).toBeInTheDocument();
  });

  it('calls onSelectBlueprint when blueprint is clicked', () => {
    const blueprints = [
      createMockBlueprint({ id: '1', blueprint_name: 'Blueprint 1' }),
    ];

    render(
      <BlueprintList
        blueprints={blueprints}
        selectedBlueprint={null}
        onSelectBlueprint={mockOnSelectBlueprint}
      />
    );

    fireEvent.click(screen.getByText('Blueprint 1'));
    expect(mockOnSelectBlueprint).toHaveBeenCalledWith(blueprints[0]);
  });

  it('applies selected class to selected blueprint', () => {
    const blueprints = [
      createMockBlueprint({ id: '1', blueprint_name: 'Blueprint 1' }),
      createMockBlueprint({ id: '2', blueprint_name: 'Blueprint 2' }),
    ];
    const selectedBlueprint = blueprints[0];

    render(
      <BlueprintList
        blueprints={blueprints}
        selectedBlueprint={selectedBlueprint}
        onSelectBlueprint={mockOnSelectBlueprint}
      />
    );

    const selectedItem = screen.getByText('Blueprint 1').closest('li');
    const unselectedItem = screen.getByText('Blueprint 2').closest('li');

    expect(selectedItem).toHaveClass('selected');
    expect(unselectedItem).not.toHaveClass('selected');
  });

  it('applies blueprintListItem class to all items', () => {
    const blueprints = [
      createMockBlueprint({ id: '1', blueprint_name: 'Blueprint 1' }),
      createMockBlueprint({ id: '2', blueprint_name: 'Blueprint 2' }),
    ];

    render(
      <BlueprintList
        blueprints={blueprints}
        selectedBlueprint={null}
        onSelectBlueprint={mockOnSelectBlueprint}
      />
    );

    const listItems = screen.getAllByRole('listitem');
    listItems.forEach(item => {
      expect(item).toHaveClass('blueprintListItem');
    });
  });

  it('handles blueprint names with special characters', () => {
    const blueprints = [
      createMockBlueprint({ id: '1', blueprint_name: 'Blueprint with spaces & symbols' }),
    ];

    render(
      <BlueprintList
        blueprints={blueprints}
        selectedBlueprint={null}
        onSelectBlueprint={mockOnSelectBlueprint}
      />
    );

    expect(screen.getByText('Blueprint with spaces & symbols')).toBeInTheDocument();
  });

  it('handles null selectedBlueprint gracefully', () => {
    const blueprints = [
      createMockBlueprint({ id: '1', blueprint_name: 'Blueprint 1' }),
    ];

    render(
      <BlueprintList
        blueprints={blueprints}
        selectedBlueprint={null}
        onSelectBlueprint={mockOnSelectBlueprint}
      />
    );

    const listItem = screen.getByText('Blueprint 1').closest('li');
    expect(listItem).not.toHaveClass('selected');
  });

  it('handles selectedBlueprint with different ID', () => {
    const blueprints = [
      createMockBlueprint({ id: '1', blueprint_name: 'Blueprint 1' }),
      createMockBlueprint({ id: '2', blueprint_name: 'Blueprint 2' }),
    ];
    const selectedBlueprint = createMockBlueprint({ id: '3', blueprint_name: 'Different Blueprint' });

    render(
      <BlueprintList
        blueprints={blueprints}
        selectedBlueprint={selectedBlueprint}
        onSelectBlueprint={mockOnSelectBlueprint}
      />
    );

    const listItems = screen.getAllByRole('listitem');
    listItems.forEach(item => {
      expect(item).not.toHaveClass('selected');
    });
  });
});
