/**
 * Error Codes Tests
 *
 * Tests for error code constants, category mapping, and retryability.
 */

import { describe, expect, it } from 'vitest';

import {
  ERROR_CATEGORY,
  FOUNDATION_ERROR_CODE,
  getErrorCategory,
  isRetryableErrorCode,
  type FoundationErrorCode,
} from './error-codes';

// =============================================================================
// Constants
// =============================================================================

describe('FoundationErrorCode', () => {
  it('should define bridge error codes', () => {
    expect(FOUNDATION_ERROR_CODE.BRIDGE_QUERY_TIMEOUT).toBe('BRIDGE_QUERY_TIMEOUT');
    expect(FOUNDATION_ERROR_CODE.BRIDGE_NOT_INITIALIZED).toBe('BRIDGE_NOT_INITIALIZED');
    expect(FOUNDATION_ERROR_CODE.BRIDGE_WORKER_ERROR).toBe('BRIDGE_WORKER_ERROR');
  });

  it('should define query error codes', () => {
    expect(FOUNDATION_ERROR_CODE.QUERY_SYNTAX_ERROR).toBe('QUERY_SYNTAX_ERROR');
    expect(FOUNDATION_ERROR_CODE.QUERY_EXECUTION_FAILED).toBe('QUERY_EXECUTION_FAILED');
  });

  it('should define network error codes', () => {
    expect(FOUNDATION_ERROR_CODE.NETWORK_REQUEST_FAILED).toBe('NETWORK_REQUEST_FAILED');
    expect(FOUNDATION_ERROR_CODE.NETWORK_TIMEOUT).toBe('NETWORK_TIMEOUT');
  });

  it('should define validation error codes', () => {
    expect(FOUNDATION_ERROR_CODE.VALIDATION_FAILED).toBe('VALIDATION_FAILED');
    expect(FOUNDATION_ERROR_CODE.VALIDATION_REQUIRED).toBe('VALIDATION_REQUIRED');
  });

  it('should define config error codes', () => {
    expect(FOUNDATION_ERROR_CODE.CONFIG_INVALID).toBe('CONFIG_INVALID');
    expect(FOUNDATION_ERROR_CODE.CONFIG_MISSING).toBe('CONFIG_MISSING');
  });
});

describe('ErrorCategory', () => {
  it('should define all categories', () => {
    expect(ERROR_CATEGORY.TRANSIENT).toBe('transient');
    expect(ERROR_CATEGORY.PERMANENT).toBe('permanent');
    expect(ERROR_CATEGORY.USER_INPUT).toBe('user_input');
    expect(ERROR_CATEGORY.INFRASTRUCTURE).toBe('infrastructure');
    expect(ERROR_CATEGORY.CONFIGURATION).toBe('configuration');
    expect(ERROR_CATEGORY.UNKNOWN).toBe('unknown');
  });

  it('should have exactly 6 categories', () => {
    expect(Object.keys(ERROR_CATEGORY)).toHaveLength(6);
  });
});

// =============================================================================
// getErrorCategory
// =============================================================================

describe('getErrorCategory', () => {
  describe('transient errors', () => {
    const transientCodes = [
      FOUNDATION_ERROR_CODE.BRIDGE_QUERY_TIMEOUT,
      FOUNDATION_ERROR_CODE.BRIDGE_WORKER_POOL_EXHAUSTED,
      FOUNDATION_ERROR_CODE.BRIDGE_WORKER_ERROR,
      FOUNDATION_ERROR_CODE.NETWORK_REQUEST_FAILED,
      FOUNDATION_ERROR_CODE.NETWORK_TIMEOUT,
      FOUNDATION_ERROR_CODE.NETWORK_OFFLINE,
      FOUNDATION_ERROR_CODE.SYNC_FAILED,
      FOUNDATION_ERROR_CODE.DATABASE_CONNECTION_FAILED,
      FOUNDATION_ERROR_CODE.RESOURCE_BUSY,
    ];

    it.each(transientCodes)('should categorize %s as transient', (code) => {
      expect(getErrorCategory(code)).toBe(ERROR_CATEGORY.TRANSIENT);
    });
  });

  describe('user input errors', () => {
    const userInputCodes = [
      FOUNDATION_ERROR_CODE.VALIDATION_FAILED,
      FOUNDATION_ERROR_CODE.VALIDATION_REQUIRED,
      FOUNDATION_ERROR_CODE.VALIDATION_TYPE,
      FOUNDATION_ERROR_CODE.QUERY_SYNTAX_ERROR,
      FOUNDATION_ERROR_CODE.QUERY_INVALID_PARAMS,
    ];

    it.each(userInputCodes)('should categorize %s as user_input', (code) => {
      expect(getErrorCategory(code)).toBe(ERROR_CATEGORY.USER_INPUT);
    });
  });

  describe('configuration errors', () => {
    const configCodes = [
      FOUNDATION_ERROR_CODE.CONFIG_INVALID,
      FOUNDATION_ERROR_CODE.CONFIG_MISSING,
      FOUNDATION_ERROR_CODE.BRIDGE_NOT_INITIALIZED,
      FOUNDATION_ERROR_CODE.DATABASE_NOT_INITIALIZED,
    ];

    it.each(configCodes)('should categorize %s as configuration', (code) => {
      expect(getErrorCategory(code)).toBe(ERROR_CATEGORY.CONFIGURATION);
    });
  });

  describe('infrastructure errors', () => {
    const infraCodes = [
      FOUNDATION_ERROR_CODE.BRIDGE_INIT_FAILED,
      FOUNDATION_ERROR_CODE.BRIDGE_WASM_LOAD_FAILED,
      FOUNDATION_ERROR_CODE.DATABASE_QUOTA_EXCEEDED,
      FOUNDATION_ERROR_CODE.DATABASE_INDEXEDDB_ERROR,
    ];

    it.each(infraCodes)('should categorize %s as infrastructure', (code) => {
      expect(getErrorCategory(code)).toBe(ERROR_CATEGORY.INFRASTRUCTURE);
    });
  });

  describe('permanent errors', () => {
    const permanentCodes = [
      FOUNDATION_ERROR_CODE.BRIDGE_QUERY_CANCELLED,
      FOUNDATION_ERROR_CODE.NETWORK_REQUEST_CANCELLED,
      FOUNDATION_ERROR_CODE.QUERY_TABLE_NOT_FOUND,
      FOUNDATION_ERROR_CODE.RESOURCE_DISPOSED,
      FOUNDATION_ERROR_CODE.RESOURCE_NOT_FOUND,
      FOUNDATION_ERROR_CODE.NOT_IMPLEMENTED,
    ];

    it.each(permanentCodes)('should categorize %s as permanent', (code) => {
      expect(getErrorCategory(code)).toBe(ERROR_CATEGORY.PERMANENT);
    });
  });

  describe('unknown errors', () => {
    it('should return unknown for unrecognized codes', () => {
      expect(getErrorCategory('UNKNOWN_CODE' as FoundationErrorCode)).toBe(ERROR_CATEGORY.UNKNOWN);
    });

    it('should return unknown for internal error codes', () => {
      expect(getErrorCategory(FOUNDATION_ERROR_CODE.INTERNAL_ERROR)).toBe(ERROR_CATEGORY.UNKNOWN);
      expect(getErrorCategory(FOUNDATION_ERROR_CODE.ASSERTION_FAILED)).toBe(ERROR_CATEGORY.UNKNOWN);
    });
  });
});

// =============================================================================
// isRetryableErrorCode
// =============================================================================

describe('isRetryableErrorCode', () => {
  it('should return true for transient error codes', () => {
    expect(isRetryableErrorCode(FOUNDATION_ERROR_CODE.NETWORK_TIMEOUT)).toBe(true);
    expect(isRetryableErrorCode(FOUNDATION_ERROR_CODE.NETWORK_REQUEST_FAILED)).toBe(true);
    expect(isRetryableErrorCode(FOUNDATION_ERROR_CODE.BRIDGE_QUERY_TIMEOUT)).toBe(true);
  });

  it('should return false for non-transient error codes', () => {
    expect(isRetryableErrorCode(FOUNDATION_ERROR_CODE.VALIDATION_FAILED)).toBe(false);
    expect(isRetryableErrorCode(FOUNDATION_ERROR_CODE.CONFIG_INVALID)).toBe(false);
    expect(isRetryableErrorCode(FOUNDATION_ERROR_CODE.RESOURCE_NOT_FOUND)).toBe(false);
    expect(isRetryableErrorCode(FOUNDATION_ERROR_CODE.INTERNAL_ERROR)).toBe(false);
  });
});
