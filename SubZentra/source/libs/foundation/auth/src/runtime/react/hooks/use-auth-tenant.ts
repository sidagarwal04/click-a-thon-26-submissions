import { useMemo } from 'react';

import type { AuthTenantSnapshot, UserPermissions, UserRole } from '../../../kernel';
import { useAuthRuntimeContext } from '../auth-runtime-context';

export interface UseAuthTenantResult {
  readonly tenant: AuthTenantSnapshot | null;
  readonly tenantId: string | null;
  readonly role: UserRole | null;
  readonly permissions: UserPermissions | null;
  readonly setActiveTenant: (tenantId: string | null) => Promise<void>;
}

export const useAuthTenant = (): UseAuthTenantResult => {
  const { state, adapter } = useAuthRuntimeContext();

  return useMemo(
    () => ({
      tenant: state.tenant,
      tenantId: state.tenant?.id ?? null,
      role: state.tenant?.role ?? null,
      permissions: state.tenant?.permissions ?? null,
      setActiveTenant: adapter.setActiveTenant ?? (async () => undefined),
    }),
    [adapter.setActiveTenant, state.tenant],
  );
};
