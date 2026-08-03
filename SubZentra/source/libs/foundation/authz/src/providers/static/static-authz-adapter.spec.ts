import { describe, expect, it } from 'vitest';

import { AUTHZ_ROLE_ACTION, type AuthzScope } from '../../core';
import { createStaticAuthzAdapter } from './static-authz-adapter';

const scope: AuthzScope = {
  subjectId: 'user-1',
  tenantId: 'tenant-1',
  sessionId: 'session-1',
  provider: 'test',
  scopeKey: 'test:user-1:tenant-1:session-1',
};

describe('static authz adapter', () => {
  it('allows configured action/resource checks', () => {
    const adapter = createStaticAuthzAdapter({
      scope,
      allowed: [
        {
          action: 'view',
          resource: 'analytics',
        },
      ],
    });

    expect(adapter.check({ action: 'view', resource: 'analytics' }).allowed).toBe(true);
    expect(adapter.check({ action: 'manage', resource: 'users' }).allowed).toBe(false);
  });

  it('denies without a tenant scope by default', () => {
    const adapter = createStaticAuthzAdapter({
      allowed: [
        {
          action: 'view',
          resource: 'analytics',
        },
      ],
    });

    const decision = adapter.check({ action: 'view', resource: 'analytics' });

    expect(decision.allowed).toBe(false);
    expect(decision.reason).toBe('tenant_required');
  });

  it('supports role checks', () => {
    const adapter = createStaticAuthzAdapter({
      scope,
      roles: ['admin'],
    });

    expect(adapter.check({ action: AUTHZ_ROLE_ACTION, resource: 'admin' }).allowed).toBe(true);
    expect(adapter.check({ action: AUTHZ_ROLE_ACTION, resource: 'viewer' }).allowed).toBe(false);
  });

  it('preserves batch check order', () => {
    const adapter = createStaticAuthzAdapter({
      scope,
      allowed: [
        {
          action: 'view',
          resource: 'analytics',
        },
      ],
    });

    const decisions = adapter.checkBatch([
      { action: 'manage', resource: 'users' },
      { action: 'view', resource: 'analytics' },
    ]);

    expect(decisions.map((decision) => decision.allowed)).toEqual([false, true]);
  });
});
