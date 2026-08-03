/**
 * Base type definitions derived from Zod schemas
 * @module types/base
 */

import type { z } from 'zod';

import type {
  BaseEntitySchema,
  DateRangeSchema,
  PaginationParamsSchema,
  SoftDeleteSchema,
  SortDirectionSchema,
  TenantScopedSchema,
  TimestampsSchema,
} from '../schemas/base.schema';

/**
 * Timestamps type
 */
export type Timestamps = z.infer<typeof TimestampsSchema>;

/**
 * Base entity type with ID and timestamps
 */
export type BaseEntity = z.infer<typeof BaseEntitySchema>;

/**
 * Soft delete fields type
 */
export type SoftDelete = z.infer<typeof SoftDeleteSchema>;

/**
 * Tenant-scoped entity type
 */
export type TenantScoped = z.infer<typeof TenantScopedSchema>;

/**
 * Pagination parameters type
 */
export type PaginationParams = z.infer<typeof PaginationParamsSchema>;

/**
 * Sort direction type
 */
export type SortDirection = z.infer<typeof SortDirectionSchema>;

/**
 * Date range filter type
 */
export type DateRange = z.infer<typeof DateRangeSchema>;

/**
 * Paginated response wrapper
 */
export interface PaginatedResponse<T> {
  data: T[];
  nextCursor: string | null;
  hasMore: boolean;
  total?: number;
}

/**
 * API response wrapper
 */
export interface ApiResponse<T> {
  data: T;
  meta?: Record<string, unknown>;
}

/**
 * API error response
 */
export interface ApiError {
  code: string;
  message: string;
  details?: Record<string, unknown>;
}

/**
 * Mutation result type
 */
export interface MutationResult<T> {
  success: boolean;
  data?: T;
  error?: ApiError;
}

/**
 * Data source identifiers for query results.
 */
export const DATA_SOURCE = {
  API: 'api',
  CACHE: 'cache',
  NONE: 'none',
} as const;

/**
 * Data source identifier for query results.
 */
export type DataSource = (typeof DATA_SOURCE)[keyof typeof DATA_SOURCE];

/**
 * Data source identifier for offline metadata
 *
 * Composes {@link DataSource} with additional offline-specific sources.
 *
 * - 'api': Data from HTTP or WebSocket-backed API flows (via DataSource)
 * - 'cache': Data from local cache / TanStack Query cache (via DataSource)
 * - 'none': No data source / initial state (via DataSource)
 * - 'network': Data from network request
 * - 'offline_db': Data from offline IndexedDB storage
 */
export const OFFLINE_DATA_SOURCE = {
  ...DATA_SOURCE,
  NETWORK: 'network',
  OFFLINE_DB: 'offline_db',
} as const;

export type OfflineDataSource = (typeof OFFLINE_DATA_SOURCE)[keyof typeof OFFLINE_DATA_SOURCE];

/**
 * Offline metadata attached to queries/mutations
 */
export interface OfflineMetadata {
  isOffline: boolean;
  isStale: boolean;
  lastSyncedAt: string | null;
  source: OfflineDataSource;
}

/**
 * Entity with offline metadata
 */
export type WithOfflineMetadata<T> = T & {
  _offline?: OfflineMetadata;
};

/**
 * ID mapping for offline-created entities
 */
export interface IdMapping {
  provisionalId: string;
  serverId: string;
  tableName: string;
  mappedAt: string;
}
