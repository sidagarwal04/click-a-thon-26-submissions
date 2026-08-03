/**
 * useAuthUser Hook
 *
 * Hook for accessing the current authenticated user.
 *
 * @module hooks/use-auth-user
 */

import { useMemo } from 'react';

import type { AuthUser, UseAuthUserResult, UseRequiredAuthUserResult } from '../core/types';
import { AuthNotInitializedError } from '../errors/auth-errors';
import { useAuthContext } from '../providers/auth-context';

/**
 * Get current authenticated user
 *
 * Returns user info with loading state. User is null if not authenticated.
 *
 * @returns User info with loading state
 *
 * @example
 * ```tsx
 * const { user, isLoading, isAuthenticated } = useAuthUser();
 *
 * if (isLoading) {
 *   return <LoadingSpinner />;
 * }
 *
 * if (!isAuthenticated || !user) {
 *   return <LoginPrompt />;
 * }
 *
 * return <UserProfile user={user} />;
 * ```
 */
export const useAuthUser = (): UseAuthUserResult => {
  const { user, isLoading, isAuthenticated } = useAuthContext();

  return useMemo(
    () => ({
      user,
      isLoading,
      isAuthenticated,
    }),
    [user, isLoading, isAuthenticated],
  );
};

/**
 * Get current authenticated user (required).
 *
 * During loading (`isLoading === true`), `user` is `null`. Callers
 * **must** check `isLoading` before accessing the user object.
 *
 * Once loading completes, if the user is not authenticated this hook
 * throws `AuthNotInitializedError`.
 *
 * @returns Discriminated union: `{ user: null; isLoading: true }` while
 *          loading, or `{ user: AuthUser; isLoading: false }` when ready.
 * @throws {AuthNotInitializedError} If auth finished loading and user is
 *         not authenticated.
 *
 * @example
 * ```tsx
 * const { user, isLoading } = useRequiredAuthUser();
 *
 * if (isLoading) {
 *   // user is null here — show a spinner
 *   return <LoadingSpinner />;
 * }
 *
 * // user is guaranteed to be non-null after loading
 * return <Dashboard user={user} />;
 * ```
 */
export const useRequiredAuthUser = (): UseRequiredAuthUserResult => {
  const { user, isLoading, isAuthenticated } = useAuthContext();

  // While auth state is still resolving, return null explicitly.
  // Callers must check `isLoading` before accessing `user`.
  if (isLoading) {
    return {
      user: null as unknown as AuthUser,
      isLoading: true,
    };
  }

  if (!isAuthenticated || !user) {
    throw new AuthNotInitializedError('useRequiredAuthUser (not authenticated)');
  }

  return {
    user,
    isLoading: false,
  };
};
