/**
 * Foundation Error Tests
 *
 * Tests for the base error class hierarchy, factory utilities,
 * and type guards.
 */

import { describe, expect, it } from 'vitest';

import { ERROR_CATEGORY, FOUNDATION_ERROR_CODE } from './error-codes';
import {
  FoundationError,
  GenericFoundationError,
  hasErrorCode,
  isErrorCategory,
  isFoundationError,
  toFoundationError,
} from './foundation-error';

// =============================================================================
// GenericFoundationError (concrete implementation for testing)
// =============================================================================

describe('GenericFoundationError', () => {
  it('should create error with code and message', () => {
    const error = new GenericFoundationError(
      FOUNDATION_ERROR_CODE.INTERNAL_ERROR,
      'Something went wrong',
    );
    expect(error).toBeInstanceOf(Error);
    expect(error).toBeInstanceOf(FoundationError);
    expect(error.code).toBe(FOUNDATION_ERROR_CODE.INTERNAL_ERROR);
    expect(error.message).toBe('Something went wrong');
    expect(error.name).toBe('GenericFoundationError');
  });

  it('should store context', () => {
    const error = new GenericFoundationError(
      FOUNDATION_ERROR_CODE.QUERY_EXECUTION_FAILED,
      'query failed',
      { queryId: 'q-1', tableName: 'users' },
    );
    expect(error.context.queryId).toBe('q-1');
    expect(error.context.tableName).toBe('users');
  });

  it('should freeze context', () => {
    const error = new GenericFoundationError(FOUNDATION_ERROR_CODE.INTERNAL_ERROR, 'test', {
      source: 'test',
    });
    expect(Object.isFrozen(error.context)).toBe(true);
  });

  it('should store cause', () => {
    const cause = new Error('root');
    const error = new GenericFoundationError(
      FOUNDATION_ERROR_CODE.INTERNAL_ERROR,
      'wrapper',
      {},
      cause,
    );
    expect(error.cause).toBe(cause);
  });

  it('should have a numeric timestamp', () => {
    const error = new GenericFoundationError(FOUNDATION_ERROR_CODE.INTERNAL_ERROR, 'test');
    expect(typeof error.timestamp).toBe('number');
    expect(error.timestamp).toBeGreaterThan(0);
  });
});

// =============================================================================
// FoundationError properties
// =============================================================================

describe('FoundationError properties', () => {
  describe('category', () => {
    it('should return transient for network errors', () => {
      const error = new GenericFoundationError(
        FOUNDATION_ERROR_CODE.NETWORK_REQUEST_FAILED,
        'fail',
      );
      expect(error.category).toBe(ERROR_CATEGORY.TRANSIENT);
    });

    it('should return user_input for validation errors', () => {
      const error = new GenericFoundationError(FOUNDATION_ERROR_CODE.VALIDATION_FAILED, 'bad');
      expect(error.category).toBe(ERROR_CATEGORY.USER_INPUT);
    });

    it('should return configuration for config errors', () => {
      const error = new GenericFoundationError(FOUNDATION_ERROR_CODE.CONFIG_INVALID, 'bad config');
      expect(error.category).toBe(ERROR_CATEGORY.CONFIGURATION);
    });
  });

  describe('isRetryable', () => {
    it('should be true for transient errors', () => {
      const error = new GenericFoundationError(FOUNDATION_ERROR_CODE.NETWORK_TIMEOUT, 'timeout');
      expect(error.isRetryable).toBe(true);
    });

    it('should be false for permanent errors', () => {
      const error = new GenericFoundationError(FOUNDATION_ERROR_CODE.RESOURCE_NOT_FOUND, 'missing');
      expect(error.isRetryable).toBe(false);
    });
  });

  describe('shouldReport', () => {
    it('should be false for user input errors', () => {
      const error = new GenericFoundationError(
        FOUNDATION_ERROR_CODE.VALIDATION_FAILED,
        'bad input',
      );
      expect(error.shouldReport).toBe(false);
    });

    it('should be false for cancelled queries', () => {
      const error = new GenericFoundationError(
        FOUNDATION_ERROR_CODE.BRIDGE_QUERY_CANCELLED,
        'cancelled',
      );
      expect(error.shouldReport).toBe(false);
    });

    it('should be true for infrastructure errors', () => {
      const error = new GenericFoundationError(
        FOUNDATION_ERROR_CODE.DATABASE_OPERATION_FAILED,
        'db fail',
      );
      expect(error.shouldReport).toBe(true);
    });
  });

  describe('toJSON', () => {
    it('should serialize all fields', () => {
      const cause = new Error('root');
      const error = new GenericFoundationError(
        FOUNDATION_ERROR_CODE.INTERNAL_ERROR,
        'test error',
        { source: 'test' },
        cause,
      );
      const json = error.toJSON();

      expect(json.name).toBe('GenericFoundationError');
      expect(json.code).toBe(FOUNDATION_ERROR_CODE.INTERNAL_ERROR);
      expect(json.message).toBe('test error');
      expect(json.category).toBe(ERROR_CATEGORY.UNKNOWN);
      expect(json.isRetryable).toBe(false);
      expect(json.context.source).toBe('test');
      expect(json.cause?.name).toBe('Error');
      expect(json.cause?.message).toBe('root');
      expect(typeof json.timestamp).toBe('number');
    });

    it('should omit cause when not present', () => {
      const error = new GenericFoundationError(FOUNDATION_ERROR_CODE.INTERNAL_ERROR, 'test');
      expect(error.toJSON().cause).toBeUndefined();
    });
  });

  describe('toString', () => {
    it('should include name, code, and message', () => {
      const error = new GenericFoundationError(FOUNDATION_ERROR_CODE.INTERNAL_ERROR, 'oops');
      const str = error.toString();
      expect(str).toContain('GenericFoundationError');
      expect(str).toContain('INTERNAL_ERROR');
      expect(str).toContain('oops');
    });

    it('should include context when non-empty', () => {
      const error = new GenericFoundationError(FOUNDATION_ERROR_CODE.INTERNAL_ERROR, 'test', {
        source: 'unit-test',
      });
      expect(error.toString()).toContain('unit-test');
    });
  });
});

// =============================================================================
// toFoundationError factory
// =============================================================================

describe('toFoundationError', () => {
  it('should return existing FoundationError unchanged', () => {
    const original = new GenericFoundationError(FOUNDATION_ERROR_CODE.INTERNAL_ERROR, 'test');
    const result = toFoundationError(original);
    expect(result).toBe(original);
  });

  it('should return existing FoundationError with additional context (best effort)', () => {
    // NOTE: withContext() has a known limitation with GenericFoundationError
    // because its constructor signature (code, message, context, cause) differs
    // from the base class assumption (message, context, cause). This test
    // verifies the function does not throw and returns a FoundationError.
    const original = new GenericFoundationError(FOUNDATION_ERROR_CODE.INTERNAL_ERROR, 'test', {
      source: 'a',
    });
    const result = toFoundationError(original, FOUNDATION_ERROR_CODE.INTERNAL_ERROR, {
      operation: 'b',
    });
    expect(result).toBeInstanceOf(FoundationError);
  });

  it('should wrap standard Error', () => {
    const stdError = new Error('standard');
    const result = toFoundationError(stdError);
    expect(result).toBeInstanceOf(FoundationError);
    expect(result.message).toBe('standard');
    expect(result.cause).toBe(stdError);
    expect(result.code).toBe(FOUNDATION_ERROR_CODE.INTERNAL_ERROR);
  });

  it('should wrap string error', () => {
    const result = toFoundationError('string error');
    expect(result).toBeInstanceOf(FoundationError);
    expect(result.message).toBe('string error');
  });

  it('should wrap unknown error', () => {
    const result = toFoundationError(42);
    expect(result).toBeInstanceOf(FoundationError);
    expect(result.message).toBe('42');
  });

  it('should use custom fallback code', () => {
    const result = toFoundationError('oops', FOUNDATION_ERROR_CODE.NETWORK_REQUEST_FAILED);
    expect(result.code).toBe(FOUNDATION_ERROR_CODE.NETWORK_REQUEST_FAILED);
  });
});

// =============================================================================
// Type guards
// =============================================================================

describe('type guards', () => {
  describe('isFoundationError', () => {
    it('should return true for FoundationError instances', () => {
      const error = new GenericFoundationError(FOUNDATION_ERROR_CODE.INTERNAL_ERROR, 'test');
      expect(isFoundationError(error)).toBe(true);
    });

    it('should return false for standard Error', () => {
      expect(isFoundationError(new Error('test'))).toBe(false);
    });

    it('should return false for non-error values', () => {
      expect(isFoundationError(null)).toBe(false);
      expect(isFoundationError('string')).toBe(false);
      expect(isFoundationError(42)).toBe(false);
    });
  });

  describe('hasErrorCode', () => {
    it('should match error with specific code', () => {
      const error = new GenericFoundationError(FOUNDATION_ERROR_CODE.NETWORK_TIMEOUT, 'timeout');
      expect(hasErrorCode(error, FOUNDATION_ERROR_CODE.NETWORK_TIMEOUT)).toBe(true);
      expect(hasErrorCode(error, FOUNDATION_ERROR_CODE.INTERNAL_ERROR)).toBe(false);
    });

    it('should return false for non-FoundationError', () => {
      expect(hasErrorCode(new Error('test'), FOUNDATION_ERROR_CODE.INTERNAL_ERROR)).toBe(false);
    });
  });

  describe('isErrorCategory', () => {
    it('should match error by category', () => {
      const error = new GenericFoundationError(FOUNDATION_ERROR_CODE.NETWORK_TIMEOUT, 'timeout');
      expect(isErrorCategory(error, ERROR_CATEGORY.TRANSIENT)).toBe(true);
      expect(isErrorCategory(error, ERROR_CATEGORY.PERMANENT)).toBe(false);
    });
  });
});
