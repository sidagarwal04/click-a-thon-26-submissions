import type { UserPermissions, UserRole } from './roles';

export const AUTH_STATE = {
  INITIALIZING: 'initializing',
  AUTHENTICATED: 'authenticated',
  UNAUTHENTICATED: 'unauthenticated',
  REVALIDATING: 'revalidating',
  ERROR: 'error',
} as const;

export type AuthStateType = (typeof AUTH_STATE)[keyof typeof AUTH_STATE];

export type AuthSessionState = 'active' | 'revalidating' | 'ended';

export interface AuthPrincipal {
  readonly id: string;
  readonly email: string;
  readonly name: string | null;
  readonly firstName: string | null;
  readonly lastName: string | null;
  readonly avatarUrl: string | null;
  readonly emailVerified: boolean;
  readonly tenantId: string | null;
  readonly role: UserRole;
  readonly permissions: UserPermissions;
  readonly claims: Readonly<Record<string, unknown>>;
  readonly provider: string;
}

export interface AuthTenantSnapshot {
  readonly id: string | null;
  readonly slug: string | null;
  readonly name: string | null;
  readonly role: UserRole | null;
  readonly permissions: UserPermissions | null;
}

export interface AuthSessionSnapshot {
  readonly id: string | null;
  readonly state: AuthSessionState;
  readonly expiresAt: number | null;
  readonly lastRefreshedAt: number | null;
  readonly isAuthenticated: boolean;
  readonly tokenType: 'none' | 'cookie' | 'bearer';
}

export interface AuthScopeSnapshot {
  readonly subjectId: string | null;
  readonly tenantId: string | null;
  readonly sessionId: string | null;
  readonly provider: string;
  readonly scopeKey: string;
}

export interface AuthState {
  readonly state: AuthStateType;
  readonly isInitializing: boolean;
  readonly isLoading: boolean;
  readonly isAuthenticated: boolean;
  readonly principal: AuthPrincipal | null;
  readonly user: AuthPrincipal | null;
  readonly tenant: AuthTenantSnapshot | null;
  readonly session: AuthSessionSnapshot | null;
  readonly scope: AuthScopeSnapshot | null;
  readonly error: Error | null;
}

export interface AuthNavigationIntent {
  readonly redirectTo?: string;
}

export type AuthTransportAudience =
  | 'first_party_http'
  | 'realtime_ticket'
  | 'external_api'
  | (string & {});

export interface AuthTransportRequest {
  readonly audience?: AuthTransportAudience;
  readonly url?: string;
  readonly method?: string;
}

export type ResolvedAuthTransport =
  | {
      readonly kind: 'anonymous';
    }
  | {
      readonly kind: 'cookie';
      readonly withCredentials?: boolean;
    }
  | {
      readonly kind: 'bearer';
      readonly token: string;
      readonly scheme?: string;
      readonly withCredentials?: boolean;
    };

export interface AuthInvalidateReason {
  readonly code?: 'unauthorized' | 'forbidden' | 'session_expired' | 'scope_changed' | 'manual';
  readonly statusCode?: number;
  readonly url?: string;
  readonly message?: string;
}

export type AuthScopeListener = (scope: AuthScopeSnapshot | null) => void;
export type AuthStateListener = (state: AuthState) => void;

export interface AuthTransport {
  readonly getTransport: (request?: AuthTransportRequest) => Promise<ResolvedAuthTransport>;
  readonly getScope: () => AuthScopeSnapshot | null;
  readonly subscribeScope: (listener: AuthScopeListener) => () => void;
  readonly invalidate: (reason?: AuthInvalidateReason) => Promise<void>;
}

export interface AuthProviderAdapter extends AuthTransport {
  readonly provider: string;
  readonly getSnapshot: () => AuthState;
  readonly subscribe: (listener: AuthStateListener) => () => void;
  readonly login: (intent?: AuthNavigationIntent) => Promise<void>;
  readonly register: (intent?: AuthNavigationIntent) => Promise<void>;
  readonly logout: (intent?: AuthNavigationIntent) => Promise<void>;
  readonly refresh: () => Promise<void>;
  readonly getAccessToken: (request?: AuthTransportRequest) => Promise<string | null>;
  readonly setActiveTenant?: (tenantId: string | null) => Promise<void>;
  readonly dispose?: () => Promise<void> | void;
}

export interface AuthServerContext {
  readonly isAuthenticated: boolean;
  readonly userId: string | null;
  readonly sessionId: string | null;
  readonly tenantId: string | null;
  readonly provider: string;
  readonly claims: Readonly<Record<string, unknown>>;
}

export interface AuthServerAdapter {
  readonly getRequestAuthContext: () => Promise<AuthServerContext>;
  readonly requireAuth: () => Promise<AuthServerContext & { userId: string }>;
  readonly requireTenant: () => Promise<AuthServerContext & { userId: string; tenantId: string }>;
}
