export const USER_ROLES = {
  OWNER: 'owner',
  ADMIN: 'admin',
  MEMBER: 'member',
  VIEWER: 'viewer',
  GUEST: 'guest',
} as const;

export type UserRole = (typeof USER_ROLES)[keyof typeof USER_ROLES];

export interface UserPermissions {
  canManageUsers: boolean;
  canManageTenant: boolean;
  canViewAnalytics: boolean;
  canExportData: boolean;
  canConfigureIntegrations: boolean;
}

const ROLE_PERMISSIONS: Readonly<Record<UserRole, UserPermissions>> = {
  [USER_ROLES.OWNER]: {
    canManageUsers: true,
    canManageTenant: true,
    canViewAnalytics: true,
    canExportData: true,
    canConfigureIntegrations: true,
  },
  [USER_ROLES.ADMIN]: {
    canManageUsers: true,
    canManageTenant: false,
    canViewAnalytics: true,
    canExportData: true,
    canConfigureIntegrations: true,
  },
  [USER_ROLES.MEMBER]: {
    canManageUsers: false,
    canManageTenant: false,
    canViewAnalytics: true,
    canExportData: true,
    canConfigureIntegrations: false,
  },
  [USER_ROLES.VIEWER]: {
    canManageUsers: false,
    canManageTenant: false,
    canViewAnalytics: true,
    canExportData: false,
    canConfigureIntegrations: false,
  },
  [USER_ROLES.GUEST]: {
    canManageUsers: false,
    canManageTenant: false,
    canViewAnalytics: false,
    canExportData: false,
    canConfigureIntegrations: false,
  },
};

export const isValidRole = (role: string): role is UserRole =>
  (Object.values(USER_ROLES) as readonly string[]).includes(role);

export const getUserPermissions = (role: UserRole): UserPermissions => ROLE_PERMISSIONS[role];

export const normalizeProviderRole = (
  value: string | null | undefined,
  fallback: UserRole = USER_ROLES.VIEWER,
): UserRole => {
  if (!value) {
    return fallback;
  }

  const normalized = value.includes(':') ? value.split(':').at(-1) ?? value : value;
  return isValidRole(normalized) ? normalized : fallback;
};
