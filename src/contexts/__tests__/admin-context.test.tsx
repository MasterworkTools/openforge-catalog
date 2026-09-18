import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { AdminProvider, useAdminContext } from '../admin-context';

// Mock fetch globally
global.fetch = jest.fn();

// Test component to access context
const TestComponent = () => {
  const { state, login, logout, clearError } = useAdminContext();

  return (
    <div>
      <div data-testid="isAuthenticated">{state.isAuthenticated.toString()}</div>
      <div data-testid="isLoading">{state.isLoading.toString()}</div>
      <div data-testid="error">{state.error || 'null'}</div>
      <button data-testid="login" onClick={() => login('test-key')}>Login</button>
      <button data-testid="logout" onClick={() => logout()}>Logout</button>
      <button data-testid="clearError" onClick={() => clearError()}>Clear Error</button>
    </div>
  );
};

describe('AdminContext', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    document.cookie = '';
  });

  describe('AdminProvider', () => {
    it('should render children', () => {
      render(
        <AdminProvider>
          <div data-testid="child">Test Child</div>
        </AdminProvider>
      );

      expect(screen.getByTestId('child')).toBeInTheDocument();
    });

    it('should initialize with default state', () => {
      render(
        <AdminProvider>
          <TestComponent />
        </AdminProvider>
      );

      expect(screen.getByTestId('isAuthenticated')).toHaveTextContent('false');
      expect(screen.getByTestId('isLoading')).toHaveTextContent('true'); // Initially loading
      expect(screen.getByTestId('error')).toHaveTextContent('null');
    });

    it('should call checkSession on mount', async () => {
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: false,
      });

      render(
        <AdminProvider>
          <TestComponent />
        </AdminProvider>
      );

      await waitFor(() => {
        expect(global.fetch).toHaveBeenCalledWith('/api/admin/sessions/validate', {
          credentials: 'include',
        });
      });
    });
  });

  describe('useAdminContext', () => {
    it('should throw error when used outside provider', () => {
      // Suppress console.error for this test
      const consoleSpy = jest.spyOn(console, 'error').mockImplementation();

      expect(() => {
        render(<TestComponent />);
      }).toThrow('useAdminContext must be used within an AdminProvider');

      consoleSpy.mockRestore();
    });

    it('should provide context when used within provider', () => {
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: false,
      });

      render(
        <AdminProvider>
          <TestComponent />
        </AdminProvider>
      );

      expect(screen.getByTestId('login')).toBeInTheDocument();
      expect(screen.getByTestId('logout')).toBeInTheDocument();
      expect(screen.getByTestId('clearError')).toBeInTheDocument();
    });
  });

  describe('login function', () => {
    it('should handle successful login', async () => {
      (global.fetch as jest.Mock)
        .mockResolvedValueOnce({ ok: false }) // Initial session check
        .mockResolvedValueOnce({
          ok: true,
          json: () => Promise.resolve({ session_token: 'test-token' })
        }); // Login request

      render(
        <AdminProvider>
          <TestComponent />
        </AdminProvider>
      );

      await waitFor(() => {
        expect(screen.getByTestId('isLoading')).toHaveTextContent('false');
      });

      const loginButton = screen.getByTestId('login');
      fireEvent.click(loginButton);

      await waitFor(() => {
        expect(global.fetch).toHaveBeenCalledWith('/api/admin/sessions', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ api_key: 'test-key' }),
        });
      });
    });

    it('should handle login failure', async () => {
      (global.fetch as jest.Mock)
        .mockResolvedValueOnce({ ok: false }) // Initial session check
        .mockResolvedValueOnce({ ok: false }); // Login request

      render(
        <AdminProvider>
          <TestComponent />
        </AdminProvider>
      );

      await waitFor(() => {
        expect(screen.getByTestId('isLoading')).toHaveTextContent('false');
      });

      const loginButton = screen.getByTestId('login');
      fireEvent.click(loginButton);

      await waitFor(() => {
        expect(screen.getByTestId('error')).toHaveTextContent('Login failed');
      });
    });
  });

  describe('logout function', () => {
    it('should handle logout', async () => {
      (global.fetch as jest.Mock)
        .mockResolvedValueOnce({ ok: false }) // Initial session check
        .mockResolvedValueOnce({ ok: true }); // Logout request

      render(
        <AdminProvider>
          <TestComponent />
        </AdminProvider>
      );

      await waitFor(() => {
        expect(screen.getByTestId('isLoading')).toHaveTextContent('false');
      });

      const logoutButton = screen.getByTestId('logout');
      fireEvent.click(logoutButton);

      await waitFor(() => {
        expect(global.fetch).toHaveBeenCalledWith('/api/admin/sessions', {
          method: 'DELETE',
          credentials: 'include',
          headers: {},
        });
      });
    });
  });

  describe('clearError function', () => {
    it('should clear error state', async () => {
      (global.fetch as jest.Mock)
        .mockResolvedValueOnce({ ok: false }) // Initial session check
        .mockResolvedValueOnce({ ok: false }); // Login request to create error

      render(
        <AdminProvider>
          <TestComponent />
        </AdminProvider>
      );

      await waitFor(() => {
        expect(screen.getByTestId('isLoading')).toHaveTextContent('false');
      });

      // Trigger login to create error
      const loginButton = screen.getByTestId('login');
      fireEvent.click(loginButton);

      await waitFor(() => {
        expect(screen.getByTestId('error')).toHaveTextContent('Login failed');
      });

      // Clear error
      const clearErrorButton = screen.getByTestId('clearError');
      fireEvent.click(clearErrorButton);

      await waitFor(() => {
        expect(screen.getByTestId('error')).toHaveTextContent('null');
      });
    });
  });

  describe('session validation', () => {
    it('should set authenticated state when session is valid', async () => {
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        headers: {
          get: jest.fn().mockReturnValue('test-csrf-token'),
        },
      });

      render(
        <AdminProvider>
          <TestComponent />
        </AdminProvider>
      );

      await waitFor(() => {
        expect(screen.getByTestId('isAuthenticated')).toHaveTextContent('true');
        expect(screen.getByTestId('isLoading')).toHaveTextContent('false');
      });
    });

    it('should set unauthenticated state when session is invalid', async () => {
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: false,
      });

      render(
        <AdminProvider>
          <TestComponent />
        </AdminProvider>
      );

      await waitFor(() => {
        expect(screen.getByTestId('isAuthenticated')).toHaveTextContent('false');
        expect(screen.getByTestId('isLoading')).toHaveTextContent('false');
      });
    });

    it('should handle session check errors', async () => {
      (global.fetch as jest.Mock).mockRejectedValueOnce(new Error('Network error'));

      render(
        <AdminProvider>
          <TestComponent />
        </AdminProvider>
      );

      await waitFor(() => {
        expect(screen.getByTestId('isAuthenticated')).toHaveTextContent('false');
        expect(screen.getByTestId('isLoading')).toHaveTextContent('false');
      });
    });
  });
});
