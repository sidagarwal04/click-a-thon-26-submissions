import { useMemo, useSyncExternalStore, type ReactNode } from 'react';

import { createAuthTransport } from '../../transport';
import { AUTH_STATE, type AuthProviderAdapter } from '../../kernel';
import { AuthRuntimeContext } from './auth-runtime-context';

export interface AuthRuntimeProviderProps {
  readonly adapter: AuthProviderAdapter;
  readonly children: ReactNode;
  readonly loadingComponent?: ReactNode;
  readonly errorComponent?: ReactNode | ((error: Error) => ReactNode);
}

export const AuthRuntimeProvider = ({
  adapter,
  children,
  loadingComponent = null,
  errorComponent = null,
}: AuthRuntimeProviderProps): ReactNode => {
  const state = useSyncExternalStore(adapter.subscribe, adapter.getSnapshot, adapter.getSnapshot);
  const transport = useMemo(() => createAuthTransport(adapter), [adapter]);

  const contextValue = useMemo(
    () => ({
      state,
      adapter,
      transport,
    }),
    [adapter, state, transport],
  );

  if (state.isInitializing && loadingComponent) {
    return loadingComponent;
  }

  if (state.state === AUTH_STATE.ERROR && state.error && errorComponent) {
    return typeof errorComponent === 'function' ? errorComponent(state.error) : errorComponent;
  }

  return <AuthRuntimeContext.Provider value={contextValue}>{children}</AuthRuntimeContext.Provider>;
};
