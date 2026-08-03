/**
 * User schema definitions
 * @module schemas/user
 */

import { z } from 'zod';

import { SoftDeleteSchema, TenantScopedSchema } from './base.schema';

/**
 * User role enum
 */
export const UserRoleSchema = z.enum(['owner', 'admin', 'member', 'viewer', 'guest']);

/**
 * User status enum
 */
export const UserStatusSchema = z.enum(['active', 'inactive', 'pending', 'suspended']);

/**
 * User preferences schema
 */
export const UserPreferencesSchema = z.object({
  theme: z.enum(['light', 'dark', 'system']).default('system'),
  language: z.string().default('en'),
  timezone: z.string().default('UTC'),
  notifications: z
    .object({
      email: z.boolean().default(true),
      push: z.boolean().default(true),
      inApp: z.boolean().default(true),
    })
    .prefault({}),
  dashboard: z
    .object({
      defaultView: z.string().optional(),
      favoriteReports: z.array(z.string()).default([]),
    })
    .prefault({}),
});

/**
 * Core user schema
 */
export const UserSchema = TenantScopedSchema.extend({
  email: z.string().email(),
  name: z.string().min(1).max(255),
  avatarUrl: z.string().url().nullable().optional(),
  role: UserRoleSchema,
  status: UserStatusSchema,
  preferences: UserPreferencesSchema.prefault({}),
  lastLoginAt: z.string().datetime().nullable().optional(),
  emailVerifiedAt: z.string().datetime().nullable().optional(),
  ...SoftDeleteSchema.shape,
});

/**
 * User creation input schema
 */
export const CreateUserSchema = UserSchema.omit({
  id: true,
  createdAt: true,
  updatedAt: true,
  deletedAt: true,
  isDeleted: true,
  lastLoginAt: true,
  emailVerifiedAt: true,
}).extend({
  password: z.string().min(8).optional(), // Optional for SSO users
});

/**
 * User update input schema
 */
export const UpdateUserSchema = UserSchema.partial().omit({
  id: true,
  tenantId: true,
  createdAt: true,
  updatedAt: true,
  email: true, // Email changes require separate flow
});

/**
 * User list filters schema
 */
export const UserFiltersSchema = z.object({
  status: UserStatusSchema.optional(),
  role: UserRoleSchema.optional(),
  search: z.string().optional(),
  tenantId: z.string().uuid().optional(),
});
