import { useMemo } from 'react';

import type { UserPermissions, UserRole } from '../../../kernel';
import { useAuthRuntimeContext } from '../auth-runtime-context';

export interface UseAuthorizationResult {
  readonly role: UserRole | null;
  readonly permissions: UserPermissions | null;
  readonly hasRole: (role: UserRole | readonly UserRole[]) => boolean;
  readonly hasAnyRole: (roles: readonly UserRole[]) => boolean;
  readonly hasPermission: (permission: keyof UserPermissions) => boolean;
  readonly can: (permission: keyof UserPermissions) => boolean;
}

export const useAuthorization = (): UseAuthorizationResult => {
  const { state } = useAuthRuntimeContext();
  const role = state.principal?.role ?? null;
  const permissions = state.principal?.permissions ?? null;

  return useMemo(
    () => ({
      role,
      permissions,
      hasRole: (targetRole: UserRole | readonly UserRole[]) => {
        if (!role) {
          return false;
        }

        return Array.isArray(targetRole) ? targetRole.includes(role) : role === targetRole;
      },
      hasAnyRole: (roles: readonly UserRole[]) => (role ? roles.includes(role) : false),
      hasPermission: (permission: keyof UserPermissions) => permissions?.[permission] === true,
      can: (permission: keyof UserPermissions) => permissions?.[permission] === true,
    }),
    [permissions, role],
  );
};
