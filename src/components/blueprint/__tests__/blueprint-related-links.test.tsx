import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import BlueprintRelatedLinks from '../blueprint-related-links';

describe('BlueprintRelatedLinks', () => {
  it('calls onSwap with correct tagType', () => {
    const onSwap = jest.fn();
    render(<BlueprintRelatedLinks onSwap={onSwap} />);
    fireEvent.click(screen.getByText('textures'));
    expect(onSwap).toHaveBeenCalledWith(expect.any(Object), 'texture');
    fireEvent.click(screen.getByText('sizes'));
    expect(onSwap).toHaveBeenCalledWith(expect.any(Object), 'size');
    fireEvent.click(screen.getByText('connections'));
    expect(onSwap).toHaveBeenCalledWith(expect.any(Object), 'connection');
  });

  it('renders all related links', () => {
    render(<BlueprintRelatedLinks onSwap={jest.fn()} />);
    expect(screen.getByText('textures')).toBeInTheDocument();
    expect(screen.getByText('sizes')).toBeInTheDocument();
    expect(screen.getByText('connections')).toBeInTheDocument();
  });
});
