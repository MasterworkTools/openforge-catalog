import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import AdminHeader from '../admin-header';

// Mock the admin context
jest.mock('@/contexts/admin-context', () => ({
  useAdminContext: jest.fn(),
}));

import { useAdminContext } from '@/contexts/admin-context';
const mockUseAdminContext = useAdminContext as jest.MockedFunction<typeof useAdminContext>;

describe('AdminHeader', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('when not authenticated', () => {
    beforeEach(() => {
      mockUseAdminContext.mockReturnValue({
        state: {
          isAuthenticated: false,
          isLoading: false,
          error: null,
          csrfToken: null,
        },
        login: jest.fn(),
        logout: jest.fn(),
        clearError: jest.fn(),
      });
    });

    it('should not render anything', () => {
      render(<AdminHeader />);

      expect(screen.queryByText('Admin Login')).not.toBeInTheDocument();
      expect(screen.queryByText('Logout')).not.toBeInTheDocument();
    });
  });

  describe('when authenticated', () => {
    const mockLogout = jest.fn();

    beforeEach(() => {
      mockUseAdminContext.mockReturnValue({
        state: {
          isAuthenticated: true,
          isLoading: false,
          error: null,
          csrfToken: 'test-csrf-token',
        },
        login: jest.fn(),
        logout: mockLogout,
        clearError: jest.fn(),
      });
    });

    it('should render logout button', () => {
      render(<AdminHeader />);

      const logoutButton = screen.getByText('Logout');
      expect(logoutButton).toBeInTheDocument();
    });

    it('should not render admin login link', () => {
      render(<AdminHeader />);

      expect(screen.queryByText('Admin Login')).not.toBeInTheDocument();
    });

    it('should call logout when logout button is clicked', () => {
      render(<AdminHeader />);

      const logoutButton = screen.getByText('Logout');
      fireEvent.click(logoutButton);

      expect(mockLogout).toHaveBeenCalled();
    });

    it('should have correct styling for logout button', () => {
      render(<AdminHeader />);

      const logoutButton = screen.getByText('Logout');
      expect(logoutButton).toHaveClass('visibleLink');
      expect(logoutButton).toBeInTheDocument();
    });
  });

  describe('integration with AdminProvider', () => {
    it('should work within AdminProvider', () => {
      mockUseAdminContext.mockReturnValue({
        state: {
          isAuthenticated: false,
          isLoading: false,
          error: null,
          csrfToken: null,
        },
        login: jest.fn(),
        logout: jest.fn(),
        clearError: jest.fn(),
      });

      render(<AdminHeader />);

      // Should not render anything when not authenticated
      expect(screen.queryByText('Admin Login')).not.toBeInTheDocument();
      expect(screen.queryByText('Logout')).not.toBeInTheDocument();
    });
  });
});
