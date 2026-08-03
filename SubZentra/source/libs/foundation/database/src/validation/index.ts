/**
 * Validation exports
 *
 * NOTE: Validators return Result<T, ZodValidationError> from @foundation/data-model
 *
 * @module validation
 */

export { assertValid } from './assert-valid';

export {
  // Schemas
  queryCacheEntrySchema,
  mutationQueueEntrySchema,
  opfsMetadataEntrySchema,
  syncStateEntrySchema,
  lastSyncValueSchema,
  networkStatusSchema,
  duckDBViewsValueSchema,

  // Validated types
  type ValidatedQueryCacheEntry,
  type ValidatedMutationQueueEntry,
  type ValidatedOpfsMetadataEntry,
  type ValidatedSyncStateEntry,

  // Error class
  ZodValidationError,

  // Factory
  createValidator,

  // Pre-built validators
  validateQueryCacheEntry,
  validateMutationQueueEntry,
  validateOpfsMetadataEntry,
  validateSyncStateEntry,
  validateLastSyncValue,
  validateNetworkStatus,
  validateDuckDBViewsValue,
  validateTableSyncMetadataEntry,
} from './schemas';
