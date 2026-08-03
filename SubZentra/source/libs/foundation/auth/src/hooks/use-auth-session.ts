/**
 * useAuthSession Hook
 *
 * Hook for session management.
 *
 * @module hooks/use-auth-session
 */

import { useCallback, useMemo } from 'react';

import type { UseAuthSessionResult } from '../core/types';
import { useAuthInternals } from '../providers/auth-internals-context';

/**
 * Get current session with management functions
 *
 * Provides access to session state and operations like refresh and token retrieval.
 *
 * @returns Session state and management functions
 *
 * @example
 * ```tsx
 * const { session, sessionState, getAccessToken, refresh } = useAuthSession();
 *
 * // Get token for API calls
 * const handleApiCall = async () => {
 *   const token = await getAccessToken();
 *   await fetch('/api/data', {
 *     headers: token ? { Authorization: `Bearer ${token}` } : {},
 *   });
 * };
 *
 * // Manual refresh
 * const handleRefresh = async () => {
 *   await refresh();
 * };
 *
 * return (
 *   <div>
 *     <p>Session state: {sessionState}</p>
 *     {session?.expiresAt && (
 *       <p>Expires: {new Date(session.expiresAt).toLocaleString()}</p>
 *     )}
 *   </div>
 * );
 * ```
 */
export const useAuthSession = (): UseAuthSessionResult => {
  const { state, getAccessToken, facade } = useAuthInternals();

  const refresh = useCallback(async (): Promise<void> => {
    if (facade) {
      await facade.session.refresh();
    }
  }, [facade]);

  return useMemo(
    () => ({
      session: state.session,
      isLoading: state.isLoading,
      sessionState: state.session?.state ?? null,
      getAccessToken,
      refresh,
    }),
    [state.session, state.isLoading, getAccessToken, refresh],
  );
};
