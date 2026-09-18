import React from 'react';
import { render, screen } from '@testing-library/react';
import BlueprintMeta from '../blueprint-meta';

describe('BlueprintMeta', () => {
  it('renders type, last modified, and size', () => {
    render(
      <BlueprintMeta type="model" lastModified="2024-06-01 12:00" size="1.2 MB" />
    );

    // Check for labels
    expect(screen.getByText(/Type:/)).toBeInTheDocument();
    expect(screen.getByText(/Last Modified:/)).toBeInTheDocument();
    expect(screen.getByText(/Size:/)).toBeInTheDocument();

    // Check that the component renders the expected content
    const container = screen.getByText(/Type:/).closest('p');
    expect(container).toHaveTextContent('model');
    expect(container).toHaveTextContent('2024-06-01 12:00');
    expect(container).toHaveTextContent('1.2 MB');
  });
});
