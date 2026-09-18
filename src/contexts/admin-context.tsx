'use client'

import React, { createContext, useContext, useState, useEffect } from 'react';

interface AdminState {
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;
  csrfToken: string | null;
}

interface AdminContextType {
  state: AdminState;
  login: (apiKey: string) => Promise<boolean>;
  logout: () => Promise<void>;
  clearError: () => void;
}

const AdminContext = createContext<AdminContextType | null>(null);

interface AdminProviderProps {
  children: React.ReactNode;
}

export function AdminProvider({ children }: AdminProviderProps) {
  const [state, setState] = useState<AdminState>({
    isAuthenticated: false,
    isLoading: true,
    error: null,
    csrfToken: null,
  });

  const checkSession = async () => {
    try {
      // Make validation request - browser will automatically send HttpOnly cookie
      const response = await fetch('/api/admin/sessions/validate', {
        credentials: 'include', // Include cookies in the request
      });

      if (response.ok) {
        // Extract CSRF token from response headers
        const csrfToken = response.headers.get('X-CSRF-Token');

        setState(prev => ({
          ...prev,
          isAuthenticated: true,
          isLoading: false,
          csrfToken: csrfToken,
        }));
      } else {
        setState(prev => ({
          ...prev,
          isAuthenticated: false,
          isLoading: false,
          csrfToken: null,
        }));
      }
    } catch (error) {
      console.error('Session check failed:', error);
      // Set loading to false on error
      setState(prev => ({
        ...prev,
        isAuthenticated: false,
        isLoading: false,
        csrfToken: null,
      }));
    }
  };

  const login = async (apiKey: string): Promise<boolean> => {
    setState(prev => ({ ...prev, isLoading: true, error: null }));

    try {
      const response = await fetch('/api/admin/sessions', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ api_key: apiKey }),
      });

      if (!response.ok) {
        throw new Error('Login failed');
      }

      // Extract CSRF token from response headers
      const csrfToken = response.headers.get('X-CSRF-Token');

      // Backend automatically sets HttpOnly session cookie
      setState({
        isAuthenticated: true,
        isLoading: false,
        error: null,
        csrfToken: csrfToken,
      });

      return true;
    } catch (error) {
      console.error('Login failed:', error);
      setState(prev => ({
        ...prev,
        isAuthenticated: false,
        isLoading: false,
        error: 'Login failed',
        csrfToken: null,
      }));
      return false;
    }
  };

  const logout = async () => {
    try {
      // Get current CSRF token
      const currentState = state;
      const headers: Record<string, string> = {};

      if (currentState.csrfToken) {
        headers['X-CSRF-Token'] = currentState.csrfToken;
      }

      // Send logout request to backend - browser will automatically send HttpOnly cookie
      const response = await fetch('/api/admin/sessions', {
        method: 'DELETE',
        credentials: 'include', // Include cookies in the request
        headers,
      });

      if (response.ok) {
        // Only update state if logout was successful
        setState({
          isAuthenticated: false,
          isLoading: false,
          error: null,
          csrfToken: null,
        });
      }
    } catch (error) {
      // Don't update state on error - session might still be valid, but we should log it.
      console.error('Logout request failed:', error);
    }
  };

  const clearError = () => {
    setState(prev => ({ ...prev, error: null }));
  };

  useEffect(() => {
    // Only check session on client side
    if (typeof window !== 'undefined') {
      checkSession();
    } else {
      setState(prev => ({ ...prev, isLoading: false }));
    }
  }, []);

  const contextValue: AdminContextType = {
    state,
    login,
    logout,
    clearError,
  };

  return (
    <AdminContext.Provider value={contextValue}>
      {children}
    </AdminContext.Provider>
  );
}

export function useAdminContext() {
  const context = useContext(AdminContext);
  if (!context) {
    throw new Error('useAdminContext must be used within an AdminProvider');
  }
  return context;
}
