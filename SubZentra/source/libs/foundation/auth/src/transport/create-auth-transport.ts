import type { AuthProviderAdapter, AuthTransport } from '../kernel';

export const createAuthTransport = (adapter: AuthProviderAdapter): AuthTransport => ({
  getTransport: (request) => adapter.getTransport(request),
  getScope: () => adapter.getScope(),
  subscribeScope: (listener) => adapter.subscribeScope(listener),
  invalidate: (reason) => adapter.invalidate(reason),
});

export const createAdapterAuthTransport = createAuthTransport;
