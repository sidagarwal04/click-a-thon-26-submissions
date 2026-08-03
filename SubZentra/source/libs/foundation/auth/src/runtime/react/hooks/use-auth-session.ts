import { useMemo } from 'react';

import type {
  AuthTransportRequest,
  AuthSessionSnapshot,
  AuthScopeSnapshot,
  ResolvedAuthTransport,
} from '../../../kernel';
import { useAuthRuntimeContext } from '../auth-runtime-context';

export interface UseAuthSessionResult {
  readonly session: AuthSessionSnapshot | null;
  readonly scope: AuthScopeSnapshot | null;
  readonly isLoading: boolean;
  readonly isAuthenticated: boolean;
  readonly getAccessToken: (request?: AuthTransportRequest) => Promise<string | null>;
  readonly getTransport: (request?: AuthTransportRequest) => Promise<ResolvedAuthTransport>;
  readonly refresh: () => Promise<void>;
}

export const useAuthSession = (): UseAuthSessionResult => {
  const { state, adapter } = useAuthRuntimeContext();

  return useMemo(
    () => ({
      session: state.session,
      scope: state.scope,
      isLoading: state.isLoading,
      isAuthenticated: state.isAuthenticated,
      getAccessToken: adapter.getAccessToken,
      getTransport: adapter.getTransport,
      refresh: adapter.refresh,
    }),
    [adapter, state.isAuthenticated, state.isLoading, state.scope, state.session],
  );
};
