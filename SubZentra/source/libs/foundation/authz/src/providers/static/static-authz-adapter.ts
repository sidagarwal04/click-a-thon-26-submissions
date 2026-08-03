import {
  AUTHZ_ROLE_ACTION,
  AUTHZ_STATE,
  createAuthzDecision,
  createDeniedAuthzDecision,
  createReadyAuthzSnapshot,
  type AuthzCheck,
  type AuthzDecision,
  type AuthzProviderAdapter,
  type AuthzScope,
  type AuthzSnapshot,
  type AuthzStateListener,
} from '../../core';

export interface StaticAuthzAdapterOptions {
  readonly provider?: string;
  readonly scope?: AuthzScope | null;
  readonly allowed?: readonly AuthzCheck[];
  readonly roles?: readonly string[];
  readonly requireScope?: boolean;
  readonly snapshot?: AuthzSnapshot;
}

const STATIC_PROVIDER = 'static';

const matchCheck = (target: AuthzCheck, allowed: AuthzCheck): boolean =>
  target.action === allowed.action &&
  target.resource === allowed.resource &&
  (allowed.tenantId === undefined || allowed.tenantId === target.tenantId);

export const createStaticAuthzAdapter = ({
  provider = STATIC_PROVIDER,
  scope = null,
  allowed = [],
  roles = [],
  requireScope = true,
  snapshot: initialSnapshot,
}: StaticAuthzAdapterOptions = {}): AuthzProviderAdapter => {
  let snapshot = initialSnapshot ?? createReadyAuthzSnapshot(provider, scope);
  const listeners = new Set<AuthzStateListener>();

  const emit = (): void => {
    listeners.forEach((listener) => listener(snapshot));
  };

  const deny = (reason: string, check: AuthzCheck): AuthzDecision =>
    createDeniedAuthzDecision({
      source: provider,
      reason,
      scope: snapshot.scope,
      ...(check.action === AUTHZ_ROLE_ACTION ? { roleKey: check.resource } : {}),
    });

  const check = (authzCheck: AuthzCheck): AuthzDecision => {
    if (snapshot.state !== AUTHZ_STATE.READY) {
      return deny('authz_not_ready', authzCheck);
    }

    if (requireScope && !snapshot.scope?.tenantId) {
      return deny('tenant_required', authzCheck);
    }

    if (
      authzCheck.tenantId &&
      snapshot.scope?.tenantId &&
      authzCheck.tenantId !== snapshot.scope.tenantId
    ) {
      return deny('scope_mismatch', authzCheck);
    }

    if (authzCheck.action === AUTHZ_ROLE_ACTION) {
      const roleKey = authzCheck.resource;
      const allowedRole = roles.includes(roleKey);

      return createAuthzDecision({
        allowed: allowedRole,
        source: provider,
        reason: allowedRole ? null : 'role_denied',
        scope: snapshot.scope,
        roleKey,
      });
    }

    const allowedDecision = allowed.some((candidate) => matchCheck(authzCheck, candidate));

    return createAuthzDecision({
      allowed: allowedDecision,
      source: provider,
      reason: allowedDecision ? null : 'permission_denied',
      scope: snapshot.scope,
    });
  };

  return {
    provider,
    getSnapshot: () => snapshot,
    subscribe: (listener) => {
      listeners.add(listener);
      listener(snapshot);
      return () => listeners.delete(listener);
    },
    check,
    checkBatch: (checks) => checks.map(check),
    refresh: async () => undefined,
    setScope: (nextScope) => {
      snapshot = {
        ...snapshot,
        scope: nextScope,
      };
      emit();
    },
    dispose: () => {
      listeners.clear();
    },
  };
};
