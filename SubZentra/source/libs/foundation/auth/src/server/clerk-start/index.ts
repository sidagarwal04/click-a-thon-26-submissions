import { auth, clerkMiddleware } from '@clerk/tanstack-react-start/server';

import type { AuthServerAdapter, AuthServerContext } from '../../kernel';

export class ServerAuthRequiredError extends Error {
  constructor() {
    super('Authentication is required');
    this.name = 'ServerAuthRequiredError';
  }
}

export class ServerTenantRequiredError extends Error {
  constructor() {
    super('Tenant context is required');
    this.name = 'ServerTenantRequiredError';
  }
}

const asRecord = (value: unknown): Readonly<Record<string, unknown>> =>
  value && typeof value === 'object' ? { ...(value as Record<string, unknown>) } : {};

export const getRequestAuthContext = async (): Promise<AuthServerContext> => {
  const requestAuth = await auth();

  return {
    isAuthenticated: Boolean(requestAuth.userId),
    userId: requestAuth.userId ?? null,
    sessionId: requestAuth.sessionId ?? null,
    tenantId: requestAuth.orgId ?? null,
    provider: 'clerk',
    claims: asRecord(requestAuth.sessionClaims),
  };
};

export const requireAuth = async (): Promise<AuthServerContext & { userId: string }> => {
  const context = await getRequestAuthContext();

  if (!context.userId) {
    throw new ServerAuthRequiredError();
  }

  return {
    ...context,
    userId: context.userId,
  };
};

export const requireTenant = async (): Promise<
  AuthServerContext & { userId: string; tenantId: string }
> => {
  const context = await requireAuth();

  if (!context.tenantId) {
    throw new ServerTenantRequiredError();
  }

  return {
    ...context,
    tenantId: context.tenantId,
  };
};

export const createServerAuthGateway = (): AuthServerAdapter => ({
  getRequestAuthContext,
  requireAuth,
  requireTenant,
});

export { clerkMiddleware };
