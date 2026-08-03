import { useEffect, useMemo, useSyncExternalStore, type ReactNode } from 'react';

import type { AuthzCheck, AuthzDecision, AuthzProviderAdapter, AuthzScope } from '../../core';
import { AUTHZ_STATE } from '../../core';
import { AuthzRuntimeContext } from './authz-context';

export type AuthzLoadingBehavior = 'deny';

export interface AuthzProviderProps {
  readonly adapter: AuthzProviderAdapter;
  readonly children: ReactNode;
  readonly scope?: AuthzScope | null;
  readonly loadingBehavior?: AuthzLoadingBehavior;
  readonly onDecision?: (decision: AuthzDecision, check: AuthzCheck) => void;
  readonly onError?: (error: Error) => void;
}

export const AuthzProvider = ({
  adapter,
  children,
  scope,
  onDecision,
  onError,
}: AuthzProviderProps): ReactNode => {
  const snapshot = useSyncExternalStore(
    adapter.subscribe,
    adapter.getSnapshot,
    adapter.getSnapshot,
  );

  useEffect(() => {
    if (scope !== undefined && adapter.setScope) {
      adapter.setScope(scope);
    }
  }, [adapter, scope]);

  useEffect(() => {
    if (snapshot.state === AUTHZ_STATE.ERROR && snapshot.error) {
      onError?.(snapshot.error);
    }
  }, [onError, snapshot.error, snapshot.state]);

  const contextValue = useMemo(
    () => ({
      snapshot,
      adapter,
      onDecision,
    }),
    [adapter, onDecision, snapshot],
  );

  return (
    <AuthzRuntimeContext.Provider value={contextValue}>{children}</AuthzRuntimeContext.Provider>
  );
};
