/**
 * useAuth Hook
 *
 * Main authentication hook for app components.
 *
 * @module hooks/use-auth
 */

import { useMemo } from 'react';

import type { UseAuthResult } from '../core/types';
import { useAuthContext } from '../providers/auth-context';
import { useAuthInternals } from '../providers/auth-internals-context';

/**
 * Main authentication hook
 *
 * Provides authentication state and actions for app components.
 *
 * @returns Auth state and actions
 *
 * @example
 * ```tsx
 * const {
 *   isAuthenticated,
 *   isLoading,
 *   user,
 *   login,
 *   logout,
 *   hasPermission,
 *   hasRole,
 * } = useAuth();
 *
 * if (isLoading) {
 *   return <LoadingSpinner />;
 * }
 *
 * if (!isAuthenticated) {
 *   return <button onClick={() => login()}>Login</button>;
 * }
 *
 * return (
 *   <div>
 *     <p>Welcome, {user.name}</p>
 *     {hasPermission('canManageUsers') && <AdminPanel />}
 *     <button onClick={() => logout()}>Logout</button>
 *   </div>
 * );
 * ```
 */
export const useAuth = (): UseAuthResult => {
  const context = useAuthContext();
  const internals = useAuthInternals();

  return useMemo(
    () => ({
      ...context,
      state: internals.state.state,
    }),
    [context, internals.state.state],
  );
};
