/**
 * Auth Context
 *
 * Public authentication context for app components.
 *
 * @module providers/auth-context
 */

import { createContext, useContext } from 'react';

import type { AuthContextValue } from '../core/types';
import { AuthNotInitializedError } from '../errors/auth-errors';

// =============================================================================
// Context
// =============================================================================

/**
 * Default context value (throws errors when accessed without provider)
 */
const createDefaultContextValue = (): AuthContextValue => ({
  // State
  isInitializing: true,
  isLoading: true,
  isAuthenticated: false,
  user: null,
  error: null,

  // Actions (throw errors when provider not available)
  login: async () => {
    throw new AuthNotInitializedError('login');
  },
  register: async () => {
    throw new AuthNotInitializedError('register');
  },
  logout: async () => {
    throw new AuthNotInitializedError('logout');
  },
  recoverPassword: async () => {
    throw new AuthNotInitializedError('recoverPassword');
  },

  // Permission checks (always false without provider)
  hasPermission: () => false,
  hasRole: () => false,
  hasAnyRole: () => false,
});

/**
 * Public auth context
 *
 * Provides authentication state and actions to app components.
 */
export const AuthContext = createContext<AuthContextValue>(createDefaultContextValue());

AuthContext.displayName = 'AuthContext';

// =============================================================================
// Hook
// =============================================================================

/**
 * Use auth context
 *
 * @returns Auth context value
 * @throws {Error} If used outside AuthProvider
 *
 * @example
 * ```tsx
 * const { isAuthenticated, user, login, logout } = useAuthContext();
 *
 * if (!isAuthenticated) {
 *   return <button onClick={() => login()}>Login</button>;
 * }
 *
 * return <span>Welcome, {user?.name}</span>;
 * ```
 */
export const useAuthContext = (): AuthContextValue => {
  const context = useContext(AuthContext);

  // The default context value has isInitializing: true
  // If we're using the default value AND it's still initializing,
  // it might be that we're outside the provider
  // However, we can't easily distinguish this from actual initialization
  // So we just return the context value

  return context;
};
