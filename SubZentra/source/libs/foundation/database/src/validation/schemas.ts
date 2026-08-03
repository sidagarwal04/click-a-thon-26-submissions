/**
 * Validation Schemas
 *
 * Zod schemas for validating database entries.
 * Uses reusable base schemas following DRY principle.
 *
 * @module validation/schemas
 */

import { z } from 'zod';

import {
  CONFLICT_STRATEGY,
  MUTATION_STATUS,
  MUTATION_TYPE,
  OPFS_FILE_TYPE,
  realtimeCursorStoreSchema,
  Result,
} from '@open-zentra/foundation-data-model';

// =============================================================================
// Reusable Base Schemas (DRY)
// =============================================================================

const timestampSchema = z.number().positive();
const nonNegativeTimestampSchema = z.number().min(0);
const nonEmptyStringSchema = z.string().min(1);
const optionalStringSchema = z.string().optional();

// =============================================================================
// Query Cache Entry Schema
// =============================================================================

export const queryCacheEntrySchema = z.object({
  queryHash: nonEmptyStringSchema,
  queryKey: z.array(z.unknown()),
  tableName: nonEmptyStringSchema,
  data: z.unknown(),
  dataUpdatedAt: timestampSchema,
  expiresAt: timestampSchema,
  schemaVersion: z.number().int().positive(),
  isOfflineData: z.boolean(),
  etag: optionalStringSchema,
});

export type ValidatedQueryCacheEntry = z.infer<typeof queryCacheEntrySchema>;

// =============================================================================
// Mutation Queue Entry Schema
// =============================================================================

const mutationStatusSchema = z.enum([
  MUTATION_STATUS.PENDING,
  MUTATION_STATUS.IN_PROGRESS,
  MUTATION_STATUS.COMPLETED,
  MUTATION_STATUS.FAILED,
  MUTATION_STATUS.OFFLINE_QUEUED,
]);

const mutationTypeSchema = z.enum([
  MUTATION_TYPE.CREATE,
  MUTATION_TYPE.UPDATE,
  MUTATION_TYPE.DELETE,
]);

// Uses ConflictStrategy const from @foundation/data-model for consistency
const conflictStrategySchema = z.enum([
  CONFLICT_STRATEGY.SERVER_WINS,
  CONFLICT_STRATEGY.CLIENT_WINS,
  CONFLICT_STRATEGY.LAST_WRITE_WINS,
  CONFLICT_STRATEGY.MERGE,
  CONFLICT_STRATEGY.MANUAL,
]);

export const mutationQueueEntrySchema = z.object({
  id: nonEmptyStringSchema,
  idempotencyKey: nonEmptyStringSchema,
  timestamp: timestampSchema,
  status: mutationStatusSchema,
  type: mutationTypeSchema,
  tableName: nonEmptyStringSchema,
  entityId: nonEmptyStringSchema,
  payload: z.unknown(),
  optimisticData: z.unknown().optional(),
  previousData: z.unknown().optional(),
  retryCount: z.number().int().min(0),
  lastError: optionalStringSchema,
  serverId: optionalStringSchema,
  invalidateKeys: z.array(z.string()).optional(),
  dependsOn: z.array(z.string()).optional(),
  conflictStrategy: conflictStrategySchema.optional(),
});

export type ValidatedMutationQueueEntry = z.infer<typeof mutationQueueEntrySchema>;

// =============================================================================
// OPFS Metadata Entry Schema
// =============================================================================

const opfsFileTypeSchema = z.enum([
  OPFS_FILE_TYPE.PARQUET,
  OPFS_FILE_TYPE.JSON,
  OPFS_FILE_TYPE.CSV,
  OPFS_FILE_TYPE.VIEW_DEFINITION,
]);

const opfsFileSchemaSchema = z.object({
  columns: z.array(
    z.object({
      name: nonEmptyStringSchema,
      type: nonEmptyStringSchema,
      nullable: z.boolean(),
    }),
  ),
});

export const opfsMetadataEntrySchema = z.object({
  path: nonEmptyStringSchema,
  tableName: nonEmptyStringSchema,
  fileType: opfsFileTypeSchema,
  sizeBytes: z.number().int().min(0),
  lastModified: timestampSchema,
  contentHash: optionalStringSchema,
  rowCount: z.number().int().min(0).optional(),
  schema: opfsFileSchemaSchema.optional(),
  isRegistered: z.boolean(),
  viewName: optionalStringSchema,
  dependencies: z.array(z.string()).optional(),
});

export type ValidatedOpfsMetadataEntry = z.infer<typeof opfsMetadataEntrySchema>;

// =============================================================================
// Sync State Entry Schema
// =============================================================================

export const syncStateEntrySchema = z.object({
  key: nonEmptyStringSchema,
  value: z.unknown(),
  updatedAt: timestampSchema,
});

export type ValidatedSyncStateEntry = z.infer<typeof syncStateEntrySchema>;

// =============================================================================
// Specific Sync State Value Schemas
// =============================================================================

export const lastSyncValueSchema = z.object({
  timestamp: timestampSchema,
  tables: z.record(z.string(), z.number()),
});

export const networkStatusSchema = z.object({
  isOnline: z.boolean(),
  lastOnlineAt: z.number().nullable(),
  lastOfflineAt: z.number().nullable(),
  connectionType: optionalStringSchema,
});

export const duckDBViewsValueSchema = z.object({
  views: z.array(
    z.object({
      name: nonEmptyStringSchema,
      sql: nonEmptyStringSchema,
      dependencies: z.array(z.string()),
    }),
  ),
  lastUpdatedAt: nonNegativeTimestampSchema,
});

export { realtimeCursorStoreSchema };

// =============================================================================
// Table Sync Metadata Entry Schema
// =============================================================================

export const tableSyncMetadataEntrySchema = z.object({
  name: nonEmptyStringSchema,
  lastIngestedAt: timestampSchema,
  loadedAt: timestampSchema,
  fileHashes: z.record(z.string(), z.string()),
  totalSize: z.number().int().min(0),
  totalRows: z.number().int().min(0),
});

export type ValidatedTableSyncMetadataEntry = z.infer<typeof tableSyncMetadataEntrySchema>;

// =============================================================================
// Generic Validator Factory (DRY)
// =============================================================================

/**
 * Error thrown when Zod validation fails
 */
export class ZodValidationError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'ZodValidationError';
  }
}

/**
 * Create a type-safe validator from a Zod schema
 * Returns a Result type for explicit error handling
 *
 * @example
 * ```typescript
 * const validator = createValidator(mySchema);
 * const result = validator(data);
 * if (result.ok) {
 *   console.log(result.value); // typed data
 * } else {
 *   console.error(result.error.message);
 * }
 * ```
 */
export const createValidator = <T>(
  schema: z.ZodSchema<T>,
): ((data: unknown) => Result<T, ZodValidationError>) => {
  return (data: unknown): Result<T, ZodValidationError> => {
    const result = schema.safeParse(data);
    if (!result.success) {
      return Result.err(new ZodValidationError(result.error.message));
    }
    return Result.ok(result.data);
  };
};

// =============================================================================
// Pre-built Validators
// =============================================================================

export const validateQueryCacheEntry = createValidator(queryCacheEntrySchema);
export const validateMutationQueueEntry = createValidator(mutationQueueEntrySchema);
export const validateOpfsMetadataEntry = createValidator(opfsMetadataEntrySchema);
export const validateSyncStateEntry = createValidator(syncStateEntrySchema);
export const validateLastSyncValue = createValidator(lastSyncValueSchema);
export const validateNetworkStatus = createValidator(networkStatusSchema);
export const validateDuckDBViewsValue = createValidator(duckDBViewsValueSchema);
export const validateTableSyncMetadataEntry = createValidator(tableSyncMetadataEntrySchema);
