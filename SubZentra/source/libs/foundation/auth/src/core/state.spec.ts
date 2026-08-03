import { describe, expect, it } from 'vitest';

import { createAuthScope, createUnauthenticatedAuthState } from './state';

describe('auth state helpers', () => {
  it('creates stable scope keys from provider, subject, tenant, and session', () => {
    const scope = createAuthScope({
      provider: 'clerk',
      subjectId: 'user_1',
      tenantId: 'org_1',
      sessionId: 'sess_1',
    });

    expect(scope).toEqual({
      provider: 'clerk',
      subjectId: 'user_1',
      tenantId: 'org_1',
      sessionId: 'sess_1',
      scopeKey: 'clerk:user_1:org_1:sess_1',
    });
  });

  it('keeps unauthenticated state scoped and non-null for safe cache partitioning', () => {
    const state = createUnauthenticatedAuthState('clerk');

    expect(state.isAuthenticated).toBe(false);
    expect(state.scope?.scopeKey).toBe('clerk:anonymous:personal:no-session');
  });
});
