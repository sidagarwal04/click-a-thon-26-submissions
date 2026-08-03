import { useMemo } from 'react';

import type {
  AuthNavigationIntent,
  AuthPrincipal,
  AuthScopeSnapshot,
  AuthSessionSnapshot,
  AuthState,
  AuthStateType,
  AuthTenantSnapshot,
  AuthTransport,
} from '../../../kernel';
import { useAuthRuntimeContext } from '../auth-runtime-context';

export interface UseAuthResult {
  readonly state: AuthStateType;
  readonly snapshot: AuthState;
  readonly isInitializing: boolean;
  readonly isLoading: boolean;
  readonly isAuthenticated: boolean;
  readonly principal: AuthPrincipal | null;
  readonly user: AuthPrincipal | null;
  readonly tenant: AuthTenantSnapshot | null;
  readonly session: AuthSessionSnapshot | null;
  readonly scope: AuthScopeSnapshot | null;
  readonly error: Error | null;
  readonly provider: string;
  readonly transport: AuthTransport;
  readonly login: (intent?: AuthNavigationIntent) => Promise<void>;
  readonly register: (intent?: AuthNavigationIntent) => Promise<void>;
  readonly logout: (intent?: AuthNavigationIntent) => Promise<void>;
  readonly refresh: () => Promise<void>;
}

export const useAuth = (): UseAuthResult => {
  const { state, adapter, transport } = useAuthRuntimeContext();

  return useMemo(
    () => ({
      state: state.state,
      snapshot: state,
      isInitializing: state.isInitializing,
      isLoading: state.isLoading,
      isAuthenticated: state.isAuthenticated,
      principal: state.principal,
      user: state.user,
      tenant: state.tenant,
      session: state.session,
      scope: state.scope,
      error: state.error,
      provider: adapter.provider,
      transport,
      login: adapter.login,
      register: adapter.register,
      logout: adapter.logout,
      refresh: adapter.refresh,
    }),
    [adapter, state, transport],
  );
};
