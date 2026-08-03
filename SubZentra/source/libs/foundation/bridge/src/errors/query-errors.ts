/**
 * Query-related error classes
 *
 * @module errors/query-errors
 */

import { FOUNDATION_ERROR_CODE } from '@open-zentra/foundation-data-model';

import { BridgeError } from './base-error';

// =============================================================================
// SQL Validation Error
// =============================================================================

/**
 * Error thrown when SQL identifier validation fails
 */
export class SqlValidationError extends BridgeError {
  readonly code = FOUNDATION_ERROR_CODE.BRIDGE_SQL_VALIDATION_FAILED;

  constructor(readonly identifier: string, readonly reason: string) {
    super(`Invalid SQL identifier "${identifier}": ${reason}`, {
      identifier,
      reason,
    });
  }
}
