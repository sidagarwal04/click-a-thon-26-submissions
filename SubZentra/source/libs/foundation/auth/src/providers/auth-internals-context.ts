/**
 * Auth Internals Context
 *
 * Internal authentication context for hooks and internal components.
 *
 * @module providers/auth-internals-context
 */

import { createContext, useContext } from 'react';

import { AUTH_STATE } from '../core/constants';
import type { AuthConfig, AuthInternals } from '../core/types';
import { AuthNotInitializedError } from '../errors/auth-errors';

// =============================================================================
// Context
// =============================================================================

/**
 * Default config (empty)
 */
const defaultConfig: AuthConfig = {
  ory: {
    kratosUrl: '',
  },
};

/**
 * Default context value (throws errors when accessed without provider)
 */
const createDefaultInternalsValue = (): AuthInternals => ({
  facade: null,
  getAccessToken: async () => {
    throw new AuthNotInitializedError('getAccessToken');
  },
  reauthenticate: async () => {
    throw new AuthNotInitializedError('reauthenticate');
  },
  state: {
    state: AUTH_STATE.INITIALIZING,
    isInitializing: true,
    isLoading: true,
    isAuthenticated: false,
    session: null,
    user: null,
    error: null,
  },
  config: defaultConfig,
});

/**
 * Internal auth context
 *
 * Provides internal access to auth services for hooks.
 * NOT for use in app components - use AuthContext instead.
 */
export const AuthInternalsContext = createContext<AuthInternals>(createDefaultInternalsValue());

AuthInternalsContext.displayName = 'AuthInternalsContext';

// =============================================================================
// Hook
// =============================================================================

/**
 * Use auth internals context
 *
 * For internal use only. Provides access to:
 * - Auth facade (session, flow, user services)
 * - Access token retrieval
 * - Force re-authentication
 * - Raw auth state
 *
 * @returns Auth internals
 * @throws {Error} If used outside AuthProvider
 *
 * @internal
 */
export const useAuthInternals = (): AuthInternals => {
  const context = useContext(AuthInternalsContext);
  return context;
};

/**
 * Use auth internals with required facade
 *
 * Same as useAuthInternals but throws if facade is not available.
 *
 * @returns Auth internals with non-null facade
 * @throws {AuthNotInitializedError} If facade is not available
 *
 * @internal
 */
export const useRequiredAuthInternals = (): AuthInternals & {
  facade: NonNullable<AuthInternals['facade']>;
} => {
  const context = useAuthInternals();

  if (!context.facade) {
    throw new AuthNotInitializedError('useRequiredAuthInternals');
  }

  return context as AuthInternals & { facade: NonNullable<AuthInternals['facade']> };
};
