import { createContext, useContext } from 'react';

import type { AuthProviderAdapter, AuthState, AuthTransport } from '../../kernel';

export interface AuthRuntimeContextValue {
  readonly state: AuthState;
  readonly adapter: AuthProviderAdapter;
  readonly transport: AuthTransport;
}

export const AuthRuntimeContext = createContext<AuthRuntimeContextValue | null>(null);

export const useAuthRuntimeContext = (): AuthRuntimeContextValue => {
  const context = useContext(AuthRuntimeContext);

  if (!context) {
    throw new Error('useAuthRuntimeContext must be used within AuthRuntimeProvider');
  }

  return context;
};
