/**
 * Base error class for all bridge errors
 *
 * Extends FoundationError to provide consistent error handling
 * across all foundation libraries.
 *
 * Import error utilities directly from '@open-zentra/foundation-data-model':
 * - FoundationError, ErrorContext, FoundationErrorCode
 * - isFoundationError, hasErrorCode, isErrorCategory, toFoundationError
 *
 * @module errors/base-error
 */

import {
  FoundationError,
  type FoundationErrorCode,
} from '@open-zentra/foundation-data-model';

// =============================================================================
// Bridge Error Base Class
// =============================================================================

/**
 * Abstract base class for all bridge errors
 *
 * Extends FoundationError to provide consistent error handling
 * across all foundation libraries. All custom errors in the bridge
 * library should extend this class.
 *
 * @example
 * ```typescript
 * class CustomBridgeError extends BridgeError {
 *   readonly code = FOUNDATION_ERROR_CODE.BRIDGE_WORKER_ERROR;
 *
 *   constructor(workerId: string, cause?: Error) {
 *     super(`Worker ${workerId} failed`, { workerId }, cause);
 *   }
 * }
 * ```
 */
export abstract class BridgeError extends FoundationError {
  /**
   * Override with the specific error code
   */
  abstract override readonly code: FoundationErrorCode;
}

// =============================================================================
// Type Guard
// =============================================================================

/**
 * Type guard to check if an error is a BridgeError
 */
export const isBridgeError = (error: unknown): error is BridgeError => error instanceof BridgeError;
