import {
  AUTHZ_STATE,
  type AuthzDecision,
  type AuthzDecisionSource,
  type AuthzScope,
  type AuthzSnapshot,
  type AuthzState,
} from './contracts';

interface AuthzDecisionInput {
  readonly allowed: boolean;
  readonly source: AuthzDecisionSource;
  readonly scope?: AuthzScope | null;
  readonly scopeKey?: string | null;
  readonly reason?: string | null;
  readonly checkedAt?: number;
  readonly permissionKey?: string;
  readonly roleKey?: string;
}

interface AuthzSnapshotInput {
  readonly provider: string;
  readonly state: AuthzState;
  readonly scope?: AuthzScope | null;
  readonly error?: Error | null;
}

export const createAuthzDecision = ({
  allowed,
  source,
  scope,
  scopeKey,
  reason = null,
  checkedAt = Date.now(),
  permissionKey,
  roleKey,
}: AuthzDecisionInput): AuthzDecision => ({
  allowed,
  source,
  reason,
  scopeKey: scopeKey ?? scope?.scopeKey ?? null,
  checkedAt,
  ...(permissionKey ? { permissionKey } : {}),
  ...(roleKey ? { roleKey } : {}),
});

export const createDeniedAuthzDecision = (
  input: Omit<AuthzDecisionInput, 'allowed'>,
): AuthzDecision =>
  createAuthzDecision({
    ...input,
    allowed: false,
  });

export const createAuthzSnapshot = ({
  provider,
  state,
  scope = null,
  error = null,
}: AuthzSnapshotInput): AuthzSnapshot => ({
  provider,
  state,
  scope,
  error,
  isReady: state === AUTHZ_STATE.READY,
  isLoading: state === AUTHZ_STATE.INITIALIZING,
});

export const createInitializingAuthzSnapshot = (
  provider: string,
  scope: AuthzScope | null = null,
): AuthzSnapshot =>
  createAuthzSnapshot({
    provider,
    scope,
    state: AUTHZ_STATE.INITIALIZING,
  });

export const createReadyAuthzSnapshot = (
  provider: string,
  scope: AuthzScope | null,
): AuthzSnapshot =>
  createAuthzSnapshot({
    provider,
    scope,
    state: AUTHZ_STATE.READY,
  });

export const createUnauthorizedAuthzSnapshot = (
  provider: string,
  scope: AuthzScope | null = null,
): AuthzSnapshot =>
  createAuthzSnapshot({
    provider,
    scope,
    state: AUTHZ_STATE.UNAUTHORIZED,
  });

export const createErrorAuthzSnapshot = (
  provider: string,
  error: Error,
  scope: AuthzScope | null = null,
): AuthzSnapshot =>
  createAuthzSnapshot({
    provider,
    error,
    scope,
    state: AUTHZ_STATE.ERROR,
  });
