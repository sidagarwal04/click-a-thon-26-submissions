import { createContext, useContext } from 'react';

import type { AuthzCheck, AuthzDecision, AuthzProviderAdapter, AuthzSnapshot } from '../../core';

export interface AuthzRuntimeContextValue {
  readonly snapshot: AuthzSnapshot;
  readonly adapter: AuthzProviderAdapter;
  readonly onDecision?: (decision: AuthzDecision, check: AuthzCheck) => void;
}

export const AuthzRuntimeContext = createContext<AuthzRuntimeContextValue | null>(null);

export const useAuthzRuntimeContext = (): AuthzRuntimeContextValue => {
  const context = useContext(AuthzRuntimeContext);

  if (!context) {
    throw new Error('useAuthzRuntimeContext must be used within AuthzProvider');
  }

  return context;
};
