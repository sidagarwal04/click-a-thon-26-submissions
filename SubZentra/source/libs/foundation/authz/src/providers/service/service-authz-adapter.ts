import type { AuthzProviderAdapter, AuthzScope } from '../../core';

export interface ServiceAuthzAdapterOptions {
  readonly baseUrl: string;
  readonly scope: AuthzScope | null;
}

export const createServiceAuthzAdapter = (
  _options: ServiceAuthzAdapterOptions,
): AuthzProviderAdapter => {
  throw new Error('Service AuthZ adapter is not implemented in this phase');
};
