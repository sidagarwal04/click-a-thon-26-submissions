/**
 * Error exports
 *
 * NOTE: For FoundationErrorCode, import from @open-zentra/foundation-data-model
 *
 * @module errors
 */

export {
  // Base class
  DatabaseError,

  // Specific error classes
  QuotaExceededError,
  OpfsNotSupportedError,
  OpfsInitFailedError,
  ValidationError,
  ConfigInvalidError,
  NotInitializedError,
  DuplicateEntryError,

  // Factory functions
  createQuotaExceededError,
  createOpfsNotSupportedError,
  createOpfsInitFailedError,
  createValidationError,
  createConfigInvalidError,
  createNotInitializedError,
  createDuplicateEntryError,

  // Type guards
  isDatabaseError,
  isQuotaExceededError,
} from './database-errors';

// NOTE: FoundationErrorCode and hasErrorCode should be imported directly from @open-zentra/foundation-data-model
