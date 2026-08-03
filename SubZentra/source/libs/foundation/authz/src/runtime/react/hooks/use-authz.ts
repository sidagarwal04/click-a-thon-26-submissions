import { useMemo } from 'react';

import type {
  AuthzCheck,
  AuthzDecision,
  AuthzProviderAdapter,
  AuthzSnapshot,
  AuthzState,
} from '../../../core';
import { useAuthzRuntimeContext } from '../authz-context';

export interface UseAuthzResult {
  readonly state: AuthzState;
  readonly snapshot: AuthzSnapshot;
  readonly isReady: boolean;
  readonly isLoading: boolean;
  readonly provider: string;
  readonly adapter: AuthzProviderAdapter;
  readonly check: (check: AuthzCheck) => AuthzDecision;
  readonly checkBatch: (checks: readonly AuthzCheck[]) => readonly AuthzDecision[];
  readonly refresh: () => Promise<void>;
}

export const useAuthz = (): UseAuthzResult => {
  const { snapshot, adapter } = useAuthzRuntimeContext();

  return useMemo(
    () => ({
      state: snapshot.state,
      snapshot,
      isReady: snapshot.isReady,
      isLoading: snapshot.isLoading,
      provider: adapter.provider,
      adapter,
      check: adapter.check,
      checkBatch: adapter.checkBatch,
      refresh: adapter.refresh,
    }),
    [adapter, snapshot],
  );
};
