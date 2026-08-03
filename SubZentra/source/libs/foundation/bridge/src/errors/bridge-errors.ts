/**
 * Bridge and OPFS error classes
 *
 * NOTE: For OpfsNotSupportedError, import directly from '@open-zentra/foundation-database'.
 * OPFS is fundamentally a database concern, so that is the canonical source.
 *
 * @module errors/bridge-errors
 */

import { FOUNDATION_ERROR_CODE } from '@open-zentra/foundation-data-model';

import { BridgeError } from './base-error';

// =============================================================================
// Bridge Not Initialized Error
// =============================================================================

/**
 * Error thrown when trying to use an uninitialized bridge
 */
export class BridgeNotInitializedError extends BridgeError {
  readonly code = FOUNDATION_ERROR_CODE.BRIDGE_NOT_INITIALIZED;

  constructor(readonly bridgeType: string) {
    super(`${bridgeType} is not initialized. Call initialize() first.`, {
      bridgeType,
    });
  }
}

// =============================================================================
// Bridge Initialization Error
// =============================================================================

/**
 * Error thrown when bridge initialization fails
 */
export class BridgeInitializationError extends BridgeError {
  readonly code = FOUNDATION_ERROR_CODE.BRIDGE_INIT_FAILED;

  constructor(readonly bridgeType: string, cause: Error) {
    super(
      `Failed to initialize ${bridgeType}: ${cause.message}`,
      {
        bridgeType,
      },
      cause,
    );
  }
}

// =============================================================================
// OPFS Not Found Error
// =============================================================================

/**
 * Error thrown when an OPFS file is not found
 */
export class OpfsNotFoundError extends BridgeError {
  readonly code = FOUNDATION_ERROR_CODE.BRIDGE_OPFS_NOT_FOUND;

  constructor(readonly fileName: string) {
    super(`OPFS file not found: ${fileName}`, { fileName });
  }
}

// =============================================================================
// OPFS Permission Error
// =============================================================================

/**
 * Error thrown when OPFS permission is denied
 */
export class OpfsPermissionError extends BridgeError {
  readonly code = FOUNDATION_ERROR_CODE.BRIDGE_OPFS_PERMISSION_DENIED;

  constructor(readonly fileName: string, cause?: Error) {
    super(`OPFS permission denied: ${fileName}`, { fileName }, cause);
  }
}

// =============================================================================
// OPFS Write Error
// =============================================================================

/**
 * Error thrown when writing to OPFS fails
 */
export class OpfsWriteError extends BridgeError {
  readonly code = FOUNDATION_ERROR_CODE.BRIDGE_OPFS_WRITE_FAILED;

  constructor(readonly fileName: string, cause: Error) {
    super(`Failed to write OPFS file: ${fileName}`, { fileName }, cause);
  }
}

// =============================================================================
// Configuration Error
// =============================================================================

/**
 * Error thrown when configuration is invalid
 */
export class ConfigurationError extends BridgeError {
  readonly code = FOUNDATION_ERROR_CODE.CONFIG_INVALID;

  constructor(readonly configName: string, readonly validationErrors: readonly string[]) {
    super(`Invalid ${configName} configuration: ${validationErrors.join(', ')}`, {
      configName,
      validationErrors,
    });
  }
}
