/**
 * User type definitions derived from Zod schemas
 * @module types/user
 */

import type { z } from 'zod';

import type {
  CreateUserSchema,
  UpdateUserSchema,
  UserFiltersSchema,
  UserPreferencesSchema,
  UserRoleSchema,
  UserSchema,
  UserStatusSchema,
} from '../schemas/user.schema';

/**
 * User role type
 */
export type UserRole = z.infer<typeof UserRoleSchema>;

/**
 * User status type
 */
export type UserStatus = z.infer<typeof UserStatusSchema>;

/**
 * User preferences type
 */
export type UserPreferences = z.infer<typeof UserPreferencesSchema>;

/**
 * Core user type
 */
export type User = z.infer<typeof UserSchema>;

/**
 * User creation input type
 */
export type CreateUser = z.infer<typeof CreateUserSchema>;

/**
 * User update input type
 */
export type UpdateUser = z.infer<typeof UpdateUserSchema>;

/**
 * User list filters type
 */
export type UserFilters = z.infer<typeof UserFiltersSchema>;

/**
 * User with computed fields (e.g., from joins)
 */
export interface UserWithRelations extends User {
  tenant?: {
    id: string;
    name: string;
  };
  sessionsCount?: number;
  lastSession?: {
    id: string;
    startedAt: string;
  };
}

/**
 * User profile (subset for display)
 */
export const USER_PROFILE_FIELD = {
  ID: 'id',
  NAME: 'name',
  EMAIL: 'email',
  AVATAR_URL: 'avatarUrl',
  ROLE: 'role',
  STATUS: 'status',
  PREFERENCES: 'preferences',
} as const;

type UserProfileField = (typeof USER_PROFILE_FIELD)[keyof typeof USER_PROFILE_FIELD];

export type UserProfile = Pick<User, UserProfileField>;

/**
 * User permissions map
 */
export interface UserPermissions {
  canManageUsers: boolean;
  canManageTenant: boolean;
  canViewAnalytics: boolean;
  canExportData: boolean;
  canConfigureIntegrations: boolean;
}

/**
 * Get permissions for a user role
 */
export function getUserPermissions(role: UserRole): UserPermissions {
  switch (role) {
    case 'owner':
      return {
        canManageUsers: true,
        canManageTenant: true,
        canViewAnalytics: true,
        canExportData: true,
        canConfigureIntegrations: true,
      };
    case 'admin':
      return {
        canManageUsers: true,
        canManageTenant: false,
        canViewAnalytics: true,
        canExportData: true,
        canConfigureIntegrations: true,
      };
    case 'member':
      return {
        canManageUsers: false,
        canManageTenant: false,
        canViewAnalytics: true,
        canExportData: true,
        canConfigureIntegrations: false,
      };
    case 'viewer':
      return {
        canManageUsers: false,
        canManageTenant: false,
        canViewAnalytics: true,
        canExportData: false,
        canConfigureIntegrations: false,
      };
    case 'guest':
      return {
        canManageUsers: false,
        canManageTenant: false,
        canViewAnalytics: false,
        canExportData: false,
        canConfigureIntegrations: false,
      };
  }
}
