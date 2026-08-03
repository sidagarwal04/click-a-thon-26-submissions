import { useEffect, useMemo } from 'react';

import {
  AUTHZ_STATE,
  createDeniedAuthzDecision,
  type AuthzCheck,
  type AuthzDecision,
} from '../../../core';
import { useAuthzRuntimeContext } from '../authz-context';

export interface UseCanBatchResult {
  readonly allowed: readonly boolean[];
  readonly isLoading: boolean;
  readonly decisions: readonly AuthzDecision[];
}

const denyBatch = (
  checks: readonly AuthzCheck[],
  source: string,
  reason: string,
  scopeKey: string | null,
): readonly AuthzDecision[] =>
  checks.map((check) =>
    createDeniedAuthzDecision({
      source,
      reason,
      scopeKey,
      ...(check.action === 'has-role' ? { roleKey: check.resource } : {}),
    }),
  );

export const useCanBatch = (checks: readonly AuthzCheck[]): UseCanBatchResult => {
  const { snapshot, adapter, onDecision } = useAuthzRuntimeContext();

  const decisions = useMemo(() => {
    if (snapshot.state !== AUTHZ_STATE.READY) {
      return denyBatch(
        checks,
        adapter.provider,
        snapshot.state === AUTHZ_STATE.ERROR ? 'adapter_error' : 'authz_not_ready',
        snapshot.scope?.scopeKey ?? null,
      );
    }

    try {
      return adapter.checkBatch(checks);
    } catch {
      return denyBatch(checks, adapter.provider, 'adapter_error', snapshot.scope?.scopeKey ?? null);
    }
  }, [adapter, checks, snapshot.scope?.scopeKey, snapshot.state]);

  useEffect(() => {
    decisions.forEach((decision, index) => {
      const check = checks[index];

      if (check) {
        onDecision?.(decision, check);
      }
    });
  }, [checks, decisions, onDecision]);

  return useMemo(
    () => ({
      allowed: decisions.map((decision) => decision.allowed),
      isLoading: snapshot.isLoading,
      decisions,
    }),
    [decisions, snapshot.isLoading],
  );
};
