import { AUTH_STATE, type AuthScopeSnapshot, type AuthState } from './contracts';

const cleanScopePart = (value: string | null | undefined, fallback: string): string =>
  encodeURIComponent(value && value.length > 0 ? value : fallback);

export const createAuthScope = (input: {
  readonly provider: string;
  readonly subjectId: string | null;
  readonly tenantId: string | null;
  readonly sessionId: string | null;
}): AuthScopeSnapshot => {
  const provider = input.provider || 'unknown';
  const subjectId = input.subjectId ?? null;
  const tenantId = input.tenantId ?? null;
  const sessionId = input.sessionId ?? null;

  return {
    provider,
    subjectId,
    tenantId,
    sessionId,
    scopeKey: [
      cleanScopePart(provider, 'unknown'),
      cleanScopePart(subjectId, 'anonymous'),
      cleanScopePart(tenantId, 'personal'),
      cleanScopePart(sessionId, 'no-session'),
    ].join(':'),
  };
};

export const createUnauthenticatedAuthState = (provider: string): AuthState => {
  const scope = createAuthScope({
    provider,
    subjectId: null,
    tenantId: null,
    sessionId: null,
  });

  return {
    state: AUTH_STATE.UNAUTHENTICATED,
    isInitializing: false,
    isLoading: false,
    isAuthenticated: false,
    principal: null,
    user: null,
    tenant: null,
    session: {
      id: null,
      state: 'ended',
      expiresAt: null,
      lastRefreshedAt: null,
      isAuthenticated: false,
      tokenType: 'none',
    },
    scope,
    error: null,
  };
};

export const createInitializingAuthState = (provider: string): AuthState => ({
  ...createUnauthenticatedAuthState(provider),
  state: AUTH_STATE.INITIALIZING,
  isInitializing: true,
  isLoading: true,
  scope: createAuthScope({
    provider,
    subjectId: null,
    tenantId: null,
    sessionId: null,
  }),
});
