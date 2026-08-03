/**
 * Base schema definitions with common fields
 * @module schemas/base
 */

import { z } from 'zod';

/**
 * Timestamp fields present on all entities
 */
export const TimestampsSchema = z.object({
  createdAt: z.string().datetime(),
  updatedAt: z.string().datetime(),
});

/**
 * Base entity with ID and timestamps
 * Uses extend() for proper schema inheritance
 */
export const BaseEntitySchema = TimestampsSchema.extend({
  id: z.string().uuid(),
});

/**
 * Soft delete fields
 */
export const SoftDeleteSchema = z.object({
  deletedAt: z.string().datetime().nullable().optional(),
  isDeleted: z.boolean().default(false),
});

/**
 * Tenant-scoped entity base
 */
export const TenantScopedSchema = BaseEntitySchema.extend({
  tenantId: z.string().uuid(),
});

/**
 * Provisional ID prefix for offline-created entities
 */
export const PROVISIONAL_ID_PREFIX = 'provisional_';

/**
 * Check if an ID is provisional (created offline)
 */
export function isProvisionalId(id: string): boolean {
  return id.startsWith(PROVISIONAL_ID_PREFIX);
}

/**
 * Generate a provisional ID for offline entities
 */
export function generateProvisionalId(): string {
  return `${PROVISIONAL_ID_PREFIX}${crypto.randomUUID()}`;
}

/**
 * Pagination params schema
 */
export const PaginationParamsSchema = z.object({
  cursor: z.string().optional(),
  limit: z.number().int().min(1).max(100).default(20),
});

/**
 * Sort direction schema
 */
export const SortDirectionSchema = z.enum(['asc', 'desc']);

/**
 * Date range filter schema
 */
export const DateRangeSchema = z.object({
  startDate: z.string().datetime().optional(),
  endDate: z.string().datetime().optional(),
});
