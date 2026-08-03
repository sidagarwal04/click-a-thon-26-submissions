import type {
  AuthzCheck,
  AuthzDecision,
  AuthzProviderAdapter,
  AuthzScope,
  AuthzSnapshot,
  AuthzStateListener,
} from '../../core';
import { createDeniedAuthzDecision, createInitializingAuthzSnapshot } from '../../core';

interface AdapterActions {
  readonly check?: (check: AuthzCheck) => AuthzDecision;
  readonly checkBatch?: (checks: readonly AuthzCheck[]) => readonly AuthzDecision[];
  readonly refresh?: () => Promise<void>;
  readonly dispose?: () => Promise<void> | void;
}

export interface ManagedAuthzProviderAdapter extends AuthzProviderAdapter {
  readonly setSnapshot: (snapshot: AuthzSnapshot) => void;
  readonly setScope: (scope: AuthzScope | null) => void;
  readonly setActions: (actions: AdapterActions) => void;
}

const noop = async (): Promise<void> => undefined;

export const createManagedAuthzAdapter = (
  provider: string,
  initialSnapshot: AuthzSnapshot = createInitializingAuthzSnapshot(provider),
): ManagedAuthzProviderAdapter => {
  let snapshot = initialSnapshot;
  let actions: AdapterActions = {};
  const listeners = new Set<AuthzStateListener>();

  const emit = (): void => {
    listeners.forEach((listener) => listener(snapshot));
  };

  const deny = (reason: string, check?: AuthzCheck): AuthzDecision =>
    createDeniedAuthzDecision({
      source: provider,
      reason,
      scope: snapshot.scope,
      ...(check?.action === 'has-role' ? { roleKey: check.resource } : {}),
    });

  return {
    provider,
    getSnapshot: () => snapshot,
    subscribe: (listener) => {
      listeners.add(listener);
      listener(snapshot);
      return () => listeners.delete(listener);
    },
    check: (check) => actions.check?.(check) ?? deny('adapter_not_ready', check),
    checkBatch: (checks) =>
      actions.checkBatch?.(checks) ?? checks.map((check) => deny('adapter_not_ready', check)),
    refresh: () => actions.refresh?.() ?? noop(),
    dispose: () => {
      listeners.clear();
      return actions.dispose?.();
    },
    setSnapshot: (nextSnapshot) => {
      snapshot = nextSnapshot;
      emit();
    },
    setScope: (scope) => {
      snapshot = {
        ...snapshot,
        scope,
      };
      emit();
    },
    setActions: (nextActions) => {
      actions = nextActions;
    },
  };
};
