import React from 'react';
import { render, screen } from '@testing-library/react';
import TabAdmin from '../tab-admin';

// Mock the child components
jest.mock('../admin/documentation-editor', () => {
  return function MockDocumentationEditor() {
    return <div data-testid="documentation-editor">Documentation Editor</div>;
  };
});

jest.mock('../admin/deprecated-objects-manager', () => {
  return function MockDeprecatedObjectsManager() {
    return <div data-testid="deprecated-objects-manager">Deprecated Objects Manager</div>;
  };
});

describe('TabAdmin', () => {
  it('should render admin panel title', () => {
    render(<TabAdmin />);

    expect(screen.getByText('Admin Panel')).toBeInTheDocument();
  });

  it('should render sub-tabs', () => {
    render(<TabAdmin />);

    expect(screen.getByRole('button', { name: 'Documentation Editor' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Deprecated Objects' })).toBeInTheDocument();
  });

  it('should show documentation editor by default', () => {
    render(<TabAdmin />);

    expect(screen.getByTestId('documentation-editor')).toBeInTheDocument();
    expect(screen.queryByTestId('deprecated-objects-manager')).not.toBeInTheDocument();
  });

  it('should have correct CSS classes', () => {
    render(<TabAdmin />);

    const adminTab = screen.getByText('Admin Panel').closest('.admin-tab');
    const adminContent = screen.getByText('Admin Panel').closest('.admin-content');
    const adminSubTabs = screen.getByRole('button', { name: 'Documentation Editor' }).closest('.admin-sub-tabs');
    const adminSubContent = screen.getByTestId('documentation-editor').closest('.admin-sub-content');

    expect(adminTab).toBeInTheDocument();
    expect(adminContent).toBeInTheDocument();
    expect(adminSubTabs).toBeInTheDocument();
    expect(adminSubContent).toBeInTheDocument();
  });

  it('should render all expected elements', () => {
    render(<TabAdmin />);

    // Check for all text content
    expect(screen.getByText('Admin Panel')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Documentation Editor' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Deprecated Objects' })).toBeInTheDocument();
    expect(screen.getByTestId('documentation-editor')).toBeInTheDocument();
  });
});
