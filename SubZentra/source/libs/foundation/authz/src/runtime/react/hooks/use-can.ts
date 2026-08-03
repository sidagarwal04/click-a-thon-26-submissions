import { useEffect, useMemo } from 'react';

import {
  AUTHZ_STATE,
  createDeniedAuthzDecision,
  type AuthzCheck,
  type AuthzDecision,
} from '../../../core';
import { useAuthzRuntimeContext } from '../authz-context';

export interface UseCanResult {
  readonly allowed: boolean;
  readonly isLoading: boolean;
  readonly decision: AuthzDecision;
}

const denyForState = (
  check: AuthzCheck,
  source: string,
  reason: string,
  scopeKey: string | null,
): AuthzDecision =>
  createDeniedAuthzDecision({
    source,
    reason,
    scopeKey,
    ...(check.action === 'has-role' ? { roleKey: check.resource } : {}),
  });

export const useCan = (check: AuthzCheck): UseCanResult => {
  const { snapshot, adapter, onDecision } = useAuthzRuntimeContext();

  const decision = useMemo(() => {
    if (snapshot.state !== AUTHZ_STATE.READY) {
      return denyForState(
        check,
        adapter.provider,
        snapshot.state === AUTHZ_STATE.ERROR ? 'adapter_error' : 'authz_not_ready',
        snapshot.scope?.scopeKey ?? null,
      );
    }

    try {
      return adapter.check(check);
    } catch {
      return denyForState(
        check,
        adapter.provider,
        'adapter_error',
        snapshot.scope?.scopeKey ?? null,
      );
    }
  }, [adapter, check, snapshot.scope?.scopeKey, snapshot.state]);

  useEffect(() => {
    onDecision?.(decision, check);
  }, [check, decision, onDecision]);

  return useMemo(
    () => ({
      allowed: decision.allowed,
      isLoading: snapshot.isLoading,
      decision,
    }),
    [decision, snapshot.isLoading],
  );
};
