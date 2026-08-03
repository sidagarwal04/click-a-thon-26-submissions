import type {
  AuthInvalidateReason,
  AuthNavigationIntent,
  AuthProviderAdapter,
  AuthScopeListener,
  AuthScopeSnapshot,
  AuthState,
  AuthStateListener,
  AuthTransportRequest,
  ResolvedAuthTransport,
} from '../../kernel';
import { createInitializingAuthState } from '../../kernel';

interface AdapterActions {
  readonly login?: (intent?: AuthNavigationIntent) => Promise<void>;
  readonly register?: (intent?: AuthNavigationIntent) => Promise<void>;
  readonly logout?: (intent?: AuthNavigationIntent) => Promise<void>;
  readonly refresh?: () => Promise<void>;
  readonly getAccessToken?: (request?: AuthTransportRequest) => Promise<string | null>;
  readonly getTransport?: (request?: AuthTransportRequest) => Promise<ResolvedAuthTransport>;
  readonly invalidate?: (reason?: AuthInvalidateReason) => Promise<void>;
  readonly setActiveTenant?: (tenantId: string | null) => Promise<void>;
  readonly dispose?: () => Promise<void> | void;
}

export interface ManagedAuthProviderAdapter extends AuthProviderAdapter {
  readonly setSnapshot: (state: AuthState) => void;
  readonly setScope: (scope: AuthScopeSnapshot | null) => void;
  readonly setActions: (actions: AdapterActions) => void;
}

const noop = async (): Promise<void> => undefined;

const anonymousTransport: ResolvedAuthTransport = { kind: 'anonymous' };

export const createManagedAuthAdapter = (
  provider: string,
  initialState: AuthState = createInitializingAuthState(provider),
): ManagedAuthProviderAdapter => {
  let snapshot = initialState;
  let scope = initialState.scope;
  let actions: AdapterActions = {};
  const stateListeners = new Set<AuthStateListener>();
  const scopeListeners = new Set<AuthScopeListener>();

  const emitState = (): void => {
    stateListeners.forEach((listener) => listener(snapshot));
  };

  const emitScope = (): void => {
    scopeListeners.forEach((listener) => listener(scope));
  };

  return {
    provider,
    getSnapshot: () => snapshot,
    getScope: () => scope,
    subscribe: (listener) => {
      stateListeners.add(listener);
      listener(snapshot);
      return () => stateListeners.delete(listener);
    },
    subscribeScope: (listener) => {
      scopeListeners.add(listener);
      listener(scope);
      return () => scopeListeners.delete(listener);
    },
    login: (intent) => actions.login?.(intent) ?? noop(),
    register: (intent) => actions.register?.(intent) ?? noop(),
    logout: (intent) => actions.logout?.(intent) ?? noop(),
    refresh: () => actions.refresh?.() ?? noop(),
    getAccessToken: (request) => actions.getAccessToken?.(request) ?? Promise.resolve(null),
    getTransport: (request) => actions.getTransport?.(request) ?? Promise.resolve(anonymousTransport),
    invalidate: (reason) => actions.invalidate?.(reason) ?? noop(),
    setActiveTenant: (tenantId) => actions.setActiveTenant?.(tenantId) ?? noop(),
    dispose: () => {
      stateListeners.clear();
      scopeListeners.clear();
      return actions.dispose?.();
    },
    setSnapshot: (nextState) => {
      snapshot = nextState;
      scope = nextState.scope;
      emitState();
      emitScope();
    },
    setScope: (nextScope) => {
      scope = nextScope;
      snapshot = {
        ...snapshot,
        scope: nextScope,
      };
      emitScope();
      emitState();
    },
    setActions: (nextActions) => {
      actions = nextActions;
    },
  };
};
