import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import BlueprintHeader from '../blueprint-header';

describe('BlueprintHeader', () => {
  it('renders name and fullName', () => {
    render(
      <BlueprintHeader
        name="Test Name"
        fullName="Test Full Name"
        deeplink="/deeplink"
        copied={false}
        onCopy={jest.fn()}
        showDeeplink={false}
      />
    );
    expect(screen.getByText('Test Name')).toBeInTheDocument();
    expect(screen.getByTitle('Test Full Name')).toBeInTheDocument();
  });

  it('shows deeplink and copy button when showDeeplink is true', () => {
    const onCopy = jest.fn();
    render(
      <BlueprintHeader
        name="Test Name"
        fullName="Test Full Name"
        deeplink="/deeplink"
        copied={false}
        onCopy={onCopy}
        showDeeplink={true}
      />
    );
    expect(screen.getByText('deeplink')).toHaveAttribute('href', '/deeplink');
    const copyButton = screen.getByRole('button');
    fireEvent.click(copyButton);
    expect(onCopy).toHaveBeenCalled();
  });

  it('shows "url copied" title when copied is true', () => {
    render(
      <BlueprintHeader
        name="Test Name"
        fullName="Test Full Name"
        deeplink="/deeplink"
        copied={true}
        onCopy={jest.fn()}
        showDeeplink={true}
      />
    );
    expect(screen.getByTitle('url copied')).toBeInTheDocument();
  });
});
