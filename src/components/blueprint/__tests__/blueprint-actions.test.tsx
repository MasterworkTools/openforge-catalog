import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import BlueprintActions from '../blueprint-actions';

describe('BlueprintActions', () => {
  it('renders select part link when configValues is present', () => {
    const onSelectPart = jest.fn();
    render(
      <BlueprintActions
        configValues={{ partName: 'foo' }}
        onSelectPart={onSelectPart}
        showDownload={false}
        onDownload={jest.fn()}
        issueUrl="/issue"
      />
    );
    const selectLink = screen.getByText('Select This Part');
    fireEvent.click(selectLink);
    expect(onSelectPart).toHaveBeenCalled();
  });

  it('renders download link when showDownload is true and configValues is null', () => {
    const onDownload = jest.fn();
    render(
      <BlueprintActions
        configValues={null}
        onSelectPart={null}
        showDownload={true}
        onDownload={onDownload}
        issueUrl="/issue"
      />
    );
    const downloadLink = screen.getByText('Download');
    fireEvent.click(downloadLink);
    expect(onDownload).toHaveBeenCalled();
  });

  it('renders report issue link', () => {
    render(
      <BlueprintActions
        configValues={null}
        onSelectPart={null}
        showDownload={false}
        onDownload={jest.fn()}
        issueUrl="/issue"
      />
    );
    const reportLink = screen.getByText('Report Issue with this model');
    expect(reportLink).toHaveAttribute('href', '/issue');
  });
});
