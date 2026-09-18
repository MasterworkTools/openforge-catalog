import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { useRouter } from 'next/navigation';
import AdminLogin from '../admin/page';

// Mock next/navigation
jest.mock('next/navigation', () => ({
  useRouter: jest.fn(),
}));

// Mock fetch globally
global.fetch = jest.fn();

describe('AdminLogin', () => {
  const mockPush = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
    (useRouter as jest.Mock).mockReturnValue({
      push: mockPush,
    });
    document.cookie = '';
  });

  describe('when not authenticated', () => {
    beforeEach(() => {
      // Mock session check to return not authenticated
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: false,
      });
    });

    it('should render login form', async () => {
      render(<AdminLogin />);

      await waitFor(() => {
        expect(screen.getByText('Admin Login')).toBeInTheDocument();
      });
      expect(screen.getByText('Enter your credentials to access admin features')).toBeInTheDocument();
      expect(screen.getByPlaceholderText('Username')).toBeInTheDocument();
      expect(screen.getByPlaceholderText('Password')).toBeInTheDocument();
      expect(screen.getByText('Sign in')).toBeInTheDocument();
    });

    it('should have username field disabled and pre-filled with "admin"', async () => {
      render(<AdminLogin />);

      await waitFor(() => {
        const usernameField = screen.getByPlaceholderText('Username');
        expect(usernameField).toBeDisabled();
        expect(usernameField).toHaveValue('admin');
      });
    });

    it('should have password field enabled', async () => {
      render(<AdminLogin />);

      await waitFor(() => {
        const passwordField = screen.getByPlaceholderText('Password');
        expect(passwordField).not.toBeDisabled();
      });
    });

    it('should handle form submission', async () => {
      // Clear any previous mocks and set up fresh ones
      (global.fetch as jest.Mock).mockReset();
      (global.fetch as jest.Mock)
        .mockResolvedValueOnce({ ok: false }) // Session check
        .mockResolvedValueOnce({ ok: true }); // Login request

      render(<AdminLogin />);

      await waitFor(() => {
        expect(screen.getByText('Sign in')).toBeInTheDocument();
      });

      const passwordField = screen.getByPlaceholderText('Password');
      const submitButton = screen.getByText('Sign in');

      fireEvent.change(passwordField, { target: { value: 'test-api-key' } });
      fireEvent.click(submitButton);

      // Wait for the fetch call to be made
      await waitFor(() => {
        expect(global.fetch).toHaveBeenCalledWith('/api/admin/sessions', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ api_key: 'test-api-key' }),
        });
      });

      // Wait for the router to be called after successful login
      await waitFor(() => {
        expect(mockPush).toHaveBeenCalledWith('/');
      }, { timeout: 3000 });
    });

    it('should show loading state during submission', async () => {
      (global.fetch as jest.Mock).mockReset();
      (global.fetch as jest.Mock)
        .mockResolvedValueOnce({ ok: false }) // Session check
        .mockImplementation(() => new Promise(resolve => setTimeout(() => resolve({ ok: true }), 100))); // Login request

      render(<AdminLogin />);

      await waitFor(() => {
        expect(screen.getByText('Sign in')).toBeInTheDocument();
      });

      const passwordField = screen.getByPlaceholderText('Password');
      const submitButton = screen.getByText('Sign in');

      fireEvent.change(passwordField, { target: { value: 'test-api-key' } });
      fireEvent.click(submitButton);

      expect(screen.getByText('Signing in...')).toBeInTheDocument();
      expect(submitButton).toBeDisabled();
    });

    it('should handle login failure', async () => {
      (global.fetch as jest.Mock).mockReset();
      (global.fetch as jest.Mock)
        .mockResolvedValueOnce({ ok: false }) // Session check
        .mockResolvedValueOnce({ ok: false }); // Login request

      render(<AdminLogin />);

      await waitFor(() => {
        expect(screen.getByText('Sign in')).toBeInTheDocument();
      });

      const passwordField = screen.getByPlaceholderText('Password');
      const submitButton = screen.getByText('Sign in');

      fireEvent.change(passwordField, { target: { value: 'invalid-api-key' } });
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(screen.getByText('Login failed')).toBeInTheDocument();
      });
    });

    it('should render back to main interface link', async () => {
      render(<AdminLogin />);

      await waitFor(() => {
        const backLink = screen.getByText('Back to main interface');
        expect(backLink).toBeInTheDocument();
        expect(backLink).toHaveAttribute('href', '/');
      });
    });
  });

  describe('when authenticated', () => {
    beforeEach(() => {
      // Mock session check to return authenticated
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
      });
    });

    it('should redirect to home page', async () => {
      render(<AdminLogin />);

      await waitFor(() => {
        expect(mockPush).toHaveBeenCalledWith('/');
      });
    });
  });

  describe('error handling', () => {
    beforeEach(() => {
      (global.fetch as jest.Mock).mockReset();
      (global.fetch as jest.Mock)
        .mockResolvedValueOnce({ ok: false }) // Session check
        .mockResolvedValueOnce({ ok: false }); // Login request
    });

    it('should display error message', async () => {
      render(<AdminLogin />);

      await waitFor(() => {
        expect(screen.getByText('Sign in')).toBeInTheDocument();
      });

      const passwordField = screen.getByPlaceholderText('Password');
      const submitButton = screen.getByText('Sign in');

      fireEvent.change(passwordField, { target: { value: 'test-api-key' } });
      fireEvent.click(submitButton);

      // Wait for the error to appear
      await waitFor(() => {
        expect(screen.getByText('Login failed')).toBeInTheDocument();
        expect(screen.getByText('Login failed')).toHaveClass('text-red-600');
      }, { timeout: 3000 });
    });
  });

  describe('form validation', () => {
    beforeEach(() => {
      (global.fetch as jest.Mock).mockResolvedValueOnce({ ok: false });
    });

    it('should require password field', async () => {
      render(<AdminLogin />);

      await waitFor(() => {
        const passwordField = screen.getByPlaceholderText('Password');
        expect(passwordField).toHaveAttribute('required');
      });
    });

    it('should require username field', async () => {
      render(<AdminLogin />);

      await waitFor(() => {
        const usernameField = screen.getByPlaceholderText('Username');
        expect(usernameField).toHaveAttribute('required');
      });
    });
  });
});
