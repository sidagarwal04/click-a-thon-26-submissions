import type { AuthScopeSnapshot } from '@open-zentra/foundation-auth';

export const AUTHZ_STATE = {
  INITIALIZING: 'initializing',
  READY: 'ready',
  UNAUTHORIZED: 'unauthorized',
  ERROR: 'error',
} as const;

export const AUTHZ_ROLE_ACTION = 'has-role';

export type AuthzState = (typeof AUTHZ_STATE)[keyof typeof AUTHZ_STATE];
export type AuthzAction = string & {};
export type AuthzResource = string & {};
export type AuthzDecisionSource = 'clerk' | 'static' | 'service' | 'runtime' | (string & {});

export type AuthzScope = AuthScopeSnapshot;

export interface AuthzCheck {
  readonly action: AuthzAction;
  readonly resource: AuthzResource;
  readonly context?: Readonly<Record<string, unknown>>;
  readonly tenantId?: string | null;
}

export interface AuthzDecision {
  readonly allowed: boolean;
  readonly source: AuthzDecisionSource;
  readonly reason: string | null;
  readonly scopeKey: string | null;
  readonly checkedAt: number;
  readonly permissionKey?: string;
  readonly roleKey?: string;
}

export interface AuthzSnapshot {
  readonly state: AuthzState;
  readonly isReady: boolean;
  readonly isLoading: boolean;
  readonly scope: AuthzScope | null;
  readonly error: Error | null;
  readonly provider: string;
}

export type AuthzStateListener = (snapshot: AuthzSnapshot) => void;

export interface AuthzProviderAdapter {
  readonly provider: string;
  readonly getSnapshot: () => AuthzSnapshot;
  readonly subscribe: (listener: AuthzStateListener) => () => void;
  readonly check: (check: AuthzCheck) => AuthzDecision;
  readonly checkBatch: (checks: readonly AuthzCheck[]) => readonly AuthzDecision[];
  readonly refresh: () => Promise<void>;
  readonly setScope?: (scope: AuthzScope | null) => void;
  readonly dispose?: () => Promise<void> | void;
}
