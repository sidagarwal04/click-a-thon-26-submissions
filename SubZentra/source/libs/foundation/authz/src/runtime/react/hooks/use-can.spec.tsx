import { type PropsWithChildren } from 'react';

import { act, renderHook } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { type AuthzScope } from '../../../core';
import { createStaticAuthzAdapter } from '../../../providers/static';
import { AuthzProvider } from '../authz-provider';
import { useCan } from './use-can';
import { useCanBatch } from './use-can-batch';

const scopeA: AuthzScope = {
  subjectId: 'user-1',
  tenantId: 'tenant-a',
  sessionId: 'session-1',
  provider: 'test',
  scopeKey: 'test:user-1:tenant-a:session-1',
};

const scopeB: AuthzScope = {
  subjectId: 'user-1',
  tenantId: 'tenant-b',
  sessionId: 'session-1',
  provider: 'test',
  scopeKey: 'test:user-1:tenant-b:session-1',
};

describe('useCan', () => {
  it('returns a synchronous deny-by-default result while preserving the decision', () => {
    const adapter = createStaticAuthzAdapter({ scope: scopeA });
    const wrapper = ({ children }: PropsWithChildren) => (
      <AuthzProvider adapter={adapter}>{children}</AuthzProvider>
    );

    const { result } = renderHook(() => useCan({ action: 'manage', resource: 'users' }), {
      wrapper,
    });

    expect(result.current.allowed).toBe(false);
    expect(result.current.isLoading).toBe(false);
    expect(result.current.decision.reason).toBe('permission_denied');
  });

  it('rotates decisions with scope changes', () => {
    const adapter = createStaticAuthzAdapter({
      scope: scopeA,
      allowed: [
        {
          action: 'view',
          resource: 'analytics',
          tenantId: 'tenant-a',
        },
      ],
    });
    const wrapper = ({ children }: PropsWithChildren) => (
      <AuthzProvider adapter={adapter}>{children}</AuthzProvider>
    );

    const { result } = renderHook(
      () => useCan({ action: 'view', resource: 'analytics', tenantId: 'tenant-a' }),
      { wrapper },
    );

    expect(result.current.allowed).toBe(true);

    act(() => {
      adapter.setScope?.(scopeB);
    });

    expect(result.current.allowed).toBe(false);
    expect(result.current.decision.reason).toBe('scope_mismatch');
  });
});

describe('useCanBatch', () => {
  it('preserves input order', () => {
    const adapter = createStaticAuthzAdapter({
      scope: scopeA,
      allowed: [
        {
          action: 'view',
          resource: 'analytics',
        },
      ],
    });
    const wrapper = ({ children }: PropsWithChildren) => (
      <AuthzProvider adapter={adapter}>{children}</AuthzProvider>
    );

    const { result } = renderHook(
      () =>
        useCanBatch([
          { action: 'manage', resource: 'users' },
          { action: 'view', resource: 'analytics' },
        ]),
      { wrapper },
    );

    expect(result.current.allowed).toEqual([false, true]);
  });
});
