import { useMemo } from 'react';

import type { AuthPrincipal } from '../../../kernel';
import { useAuthRuntimeContext } from '../auth-runtime-context';

export interface UseAuthUserResult {
  readonly user: AuthPrincipal | null;
  readonly principal: AuthPrincipal | null;
  readonly isLoading: boolean;
  readonly isAuthenticated: boolean;
}

export const useAuthUser = (): UseAuthUserResult => {
  const { state } = useAuthRuntimeContext();

  return useMemo(
    () => ({
      user: state.user,
      principal: state.principal,
      isLoading: state.isLoading,
      isAuthenticated: state.isAuthenticated,
    }),
    [state.isAuthenticated, state.isLoading, state.principal, state.user],
  );
};
