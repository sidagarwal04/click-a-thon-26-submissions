/**
 * Database Error Types
 *
 * Database-specific error classes that extend FoundationError.
 * Uses the centralized error infrastructure from foundation-data-model.
 *
 * @module errors/database-errors
 */

import {
  FOUNDATION_ERROR_CODE,
  FoundationError,
  isFoundationError,
  type ErrorContext,
  type FoundationErrorCode,
} from '@open-zentra/foundation-data-model';

// =============================================================================
// Database Error Classes
// =============================================================================

/**
 * Base database error class
 */
export class DatabaseError extends FoundationError {
  readonly code: FoundationErrorCode;

  constructor(
    code: FoundationErrorCode,
    message: string,
    context: ErrorContext = {},
    cause?: Error,
  ) {
    super(message, { source: 'database', ...context }, cause);
    this.code = code;
  }
}

/**
 * Storage quota exceeded error
 */
export class QuotaExceededError extends DatabaseError {
  constructor(requestedBytes: number, availableBytes?: number, cause?: Error) {
    const availableMsg = availableBytes !== undefined ? `. Available: ${availableBytes} bytes` : '';
    super(
      FOUNDATION_ERROR_CODE.DATABASE_QUOTA_EXCEEDED,
      `Storage quota exceeded. Requested: ${requestedBytes} bytes${availableMsg}`,
      { requestedBytes, availableBytes },
      cause,
    );
  }
}

/**
 * OPFS not supported error
 */
export class OpfsNotSupportedError extends DatabaseError {
  constructor() {
    super(
      FOUNDATION_ERROR_CODE.DATABASE_OPFS_NOT_SUPPORTED,
      'OPFS is not supported in this environment',
    );
  }
}

/**
 * OPFS initialization failed error
 */
export class OpfsInitFailedError extends DatabaseError {
  constructor(reason: string, cause?: Error) {
    super(
      FOUNDATION_ERROR_CODE.DATABASE_OPFS_INIT_FAILED,
      `Failed to initialize OPFS: ${reason}`,
      { reason },
      cause,
    );
  }
}

/**
 * Validation error
 */
export class ValidationError extends DatabaseError {
  constructor(field: string, reason: string) {
    super(FOUNDATION_ERROR_CODE.VALIDATION_FAILED, `Validation failed for ${field}: ${reason}`, {
      field,
      reason,
    });
  }
}

/**
 * Configuration invalid error
 */
export class ConfigInvalidError extends DatabaseError {
  constructor(reason: string) {
    super(FOUNDATION_ERROR_CODE.CONFIG_INVALID, `Invalid configuration: ${reason}`, { reason });
  }
}

/**
 * Not initialized error
 */
export class NotInitializedError extends DatabaseError {
  constructor(component: string) {
    super(
      FOUNDATION_ERROR_CODE.DATABASE_NOT_INITIALIZED,
      `${component} is not initialized. Call initialize() first.`,
      { component },
    );
  }
}

/**
 * Duplicate entry error
 */
export class DuplicateEntryError extends DatabaseError {
  constructor(key: string, type: string) {
    super(
      FOUNDATION_ERROR_CODE.DATABASE_DUPLICATE_ENTRY,
      `Duplicate ${type} entry with key: ${key}`,
      {
        key,
        entryType: type,
      },
    );
  }
}

// =============================================================================
// Error Factory Functions (Const Arrow Pattern)
// =============================================================================

/**
 * Create a quota exceeded error
 */
export const createQuotaExceededError = (
  requestedBytes: number,
  availableBytes?: number,
): QuotaExceededError => {
  return new QuotaExceededError(requestedBytes, availableBytes);
};

/**
 * Create an OPFS not supported error
 */
export const createOpfsNotSupportedError = (): OpfsNotSupportedError => {
  return new OpfsNotSupportedError();
};

/**
 * Create an OPFS initialization failed error
 */
export const createOpfsInitFailedError = (reason: string, cause?: Error): OpfsInitFailedError => {
  return new OpfsInitFailedError(reason, cause);
};

/**
 * Create a validation failed error
 */
export const createValidationError = (field: string, reason: string): ValidationError => {
  return new ValidationError(field, reason);
};

/**
 * Create a config invalid error
 */
export const createConfigInvalidError = (reason: string): ConfigInvalidError => {
  return new ConfigInvalidError(reason);
};

/**
 * Create a not initialized error
 */
export const createNotInitializedError = (component: string): NotInitializedError => {
  return new NotInitializedError(component);
};

/**
 * Create a duplicate entry error
 */
export const createDuplicateEntryError = (key: string, type: string): DuplicateEntryError => {
  return new DuplicateEntryError(key, type);
};

// =============================================================================
// Type Guards
// =============================================================================

/**
 * Check if an error is a DatabaseError
 */
export const isDatabaseError = (error: unknown): error is DatabaseError => {
  return error instanceof DatabaseError;
};

// NOTE: hasErrorCode should be imported directly from @open-zentra/foundation-data-model
// Do NOT define it here to avoid duplication

/**
 * Check if error is a quota exceeded error
 */
export const isQuotaExceededError = (error: unknown): boolean => {
  // Check for DatabaseError using hasErrorCode from foundation-data-model
  if (isFoundationError(error) && error.code === FOUNDATION_ERROR_CODE.DATABASE_QUOTA_EXCEEDED)
    return true;

  // Check for native DOMException
  if (error instanceof DOMException && error.name === 'QuotaExceededError') {
    return true;
  }

  return false;
};

// NOTE: FoundationErrorCode should be imported directly from @open-zentra/foundation-data-model
// Do NOT re-export it here to maintain single source of truth
