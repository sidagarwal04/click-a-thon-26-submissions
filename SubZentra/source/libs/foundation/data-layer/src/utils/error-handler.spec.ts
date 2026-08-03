/**
 * Tests for error-handler utilities
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

// Generic error utilities should be imported from foundation-utils
import {
  formatErrorMessage,
  isAbortError,
  isErrorType,
  isNetworkError,
  normalizeError,
} from '@open-zentra/foundation-utils';

import { createScopedErrorHandler, handleError, safeAsync, tryCatchAsync } from './error-handler';

describe('error-handler utilities', () => {
  describe('normalizeError', () => {
    it('should return Error instance as-is', () => {
      const error = new Error('test error');
      expect(normalizeError(error)).toBe(error);
    });

    it('should convert string to Error', () => {
      const result = normalizeError('string error');
      expect(result).toBeInstanceOf(Error);
      expect(result.message).toBe('string error');
    });

    it('should extract message from object with message property', () => {
      const result = normalizeError({ message: 'object error' });
      expect(result).toBeInstanceOf(Error);
      expect(result.message).toBe('object error');
    });

    it('should convert number to Error', () => {
      const result = normalizeError(42);
      expect(result).toBeInstanceOf(Error);
      expect(result.message).toBe('42');
    });

    it('should convert null to Error', () => {
      const result = normalizeError(null);
      expect(result).toBeInstanceOf(Error);
      expect(result.message).toBe('null');
    });

    it('should convert undefined to Error', () => {
      const result = normalizeError(undefined);
      expect(result).toBeInstanceOf(Error);
      expect(result.message).toBe('undefined');
    });

    it('should convert boolean to Error', () => {
      const result = normalizeError(false);
      expect(result).toBeInstanceOf(Error);
      expect(result.message).toBe('false');
    });

    it('should convert array to Error', () => {
      const result = normalizeError([1, 2, 3]);
      expect(result).toBeInstanceOf(Error);
      expect(result.message).toBe('1,2,3');
    });
  });

  describe('formatErrorMessage', () => {
    it('should format message with context', () => {
      expect(formatErrorMessage('useDLGet', 'Failed to fetch')).toBe('[useDLGet] Failed to fetch');
    });

    it('should handle empty message', () => {
      expect(formatErrorMessage('Context', '')).toBe('[Context] ');
    });

    it('should handle custom context strings', () => {
      expect(formatErrorMessage('CustomHook', 'error message')).toBe('[CustomHook] error message');
    });
  });

  describe('handleError', () => {
    let consoleWarnSpy: ReturnType<typeof vi.spyOn>;
    let consoleErrorSpy: ReturnType<typeof vi.spyOn>;

    beforeEach(() => {
      consoleWarnSpy = vi.spyOn(console, 'warn').mockReturnValue(undefined);
      consoleErrorSpy = vi.spyOn(console, 'error').mockReturnValue(undefined);
    });

    afterEach(() => {
      consoleWarnSpy.mockRestore();
      consoleErrorSpy.mockRestore();
    });

    it('should log warning by default', () => {
      const error = new Error('test error');
      handleError(error, { context: 'useDLGet' });

      expect(consoleWarnSpy).toHaveBeenCalledWith(expect.any(String), '[useDLGet] test error');
      expect(consoleErrorSpy).not.toHaveBeenCalled();
    });

    it('should log error when severity is error', () => {
      const error = new Error('test error');
      handleError(error, { context: 'useDLCreate', severity: 'error' });

      expect(consoleErrorSpy).toHaveBeenCalledWith(
        expect.any(String),
        '[useDLCreate] test error',
        error,
      );
      expect(consoleWarnSpy).not.toHaveBeenCalled();
    });

    it('should include data in log when provided', () => {
      const error = new Error('test error');
      const data = { table: 'users', entityId: '123' };
      handleError(error, { context: 'useDLUpdate', data });

      expect(consoleWarnSpy).toHaveBeenCalledWith(
        expect.any(String),
        '[useDLUpdate] test error',
        data,
      );
    });

    it('should include data in error log when provided', () => {
      const error = new Error('test error');
      const data = { table: 'users' };
      handleError(error, { context: 'useDLDelete', severity: 'error', data });

      expect(consoleErrorSpy).toHaveBeenCalledWith(
        expect.any(String),
        '[useDLDelete] test error',
        data,
        error,
      );
    });

    it('should return normalized error', () => {
      const result = handleError('string error', { context: 'Test' });
      expect(result).toBeInstanceOf(Error);
      expect(result.message).toBe('string error');
    });

    it('should rethrow when rethrow option is true', () => {
      const error = new Error('test error');
      expect(() => handleError(error, { context: 'Test', rethrow: true })).toThrow('test error');
    });

    it('should not rethrow by default', () => {
      const error = new Error('test error');
      expect(() => handleError(error, { context: 'Test' })).not.toThrow();
    });
  });

  describe('createScopedErrorHandler', () => {
    let consoleWarnSpy: ReturnType<typeof vi.spyOn>;

    beforeEach(() => {
      consoleWarnSpy = vi.spyOn(console, 'warn').mockReturnValue(undefined);
    });

    afterEach(() => {
      consoleWarnSpy.mockRestore();
    });

    it('should create a handler with fixed context', () => {
      const handleHookError = createScopedErrorHandler('useDLCreate');
      const error = new Error('scoped error');
      handleHookError(error);

      expect(consoleWarnSpy).toHaveBeenCalledWith(expect.any(String), '[useDLCreate] scoped error');
    });

    it('should allow overriding options', () => {
      const handleHookError = createScopedErrorHandler('useDLGet');
      const consoleErrorSpy = vi.spyOn(console, 'error').mockReturnValue(undefined);

      const error = new Error('test');
      handleHookError(error, { severity: 'error' });

      expect(consoleErrorSpy).toHaveBeenCalled();
      consoleErrorSpy.mockRestore();
    });

    it('should return normalized error', () => {
      const handleHookError = createScopedErrorHandler('Test');
      const result = handleHookError('string error');
      expect(result).toBeInstanceOf(Error);
      expect(result.message).toBe('string error');
    });
  });

  describe('safeAsync', () => {
    let consoleWarnSpy: ReturnType<typeof vi.spyOn>;

    beforeEach(() => {
      consoleWarnSpy = vi.spyOn(console, 'warn').mockReturnValue(undefined);
    });

    afterEach(() => {
      consoleWarnSpy.mockRestore();
    });

    it('should return result on success', async () => {
      const fn = async () => 'success';
      const safeFn = safeAsync(fn, { context: 'Test' });
      const result = await safeFn();
      expect(result).toBe('success');
    });

    it('should return undefined and log on error', async () => {
      const fn = async () => {
        throw new Error('async error');
      };
      const safeFn = safeAsync(fn, { context: 'Test' });
      const result = await safeFn();

      expect(result).toBeUndefined();
      expect(consoleWarnSpy).toHaveBeenCalledWith(expect.any(String), '[Test] async error');
    });

    it('should not rethrow errors', async () => {
      const fn = async () => {
        throw new Error('should not rethrow');
      };
      const safeFn = safeAsync(fn, { context: 'Test' });

      await expect(safeFn()).resolves.toBeUndefined();
    });
  });

  describe('tryCatchAsync', () => {
    let consoleWarnSpy: ReturnType<typeof vi.spyOn>;

    beforeEach(() => {
      consoleWarnSpy = vi.spyOn(console, 'warn').mockReturnValue(undefined);
    });

    afterEach(() => {
      consoleWarnSpy.mockRestore();
    });

    it('should return result on success', async () => {
      const result = await tryCatchAsync(async () => 'success', { context: 'Test' });
      expect(result).toBe('success');
    });

    it('should return undefined on error without default', async () => {
      const result = await tryCatchAsync(
        async () => {
          throw new Error('error');
        },
        { context: 'Test' },
      );
      expect(result).toBeUndefined();
    });

    it('should return default value on error', async () => {
      const result = await tryCatchAsync(
        async () => {
          throw new Error('error');
        },
        { context: 'Test' },
        'default',
      );
      expect(result).toBe('default');
    });

    it('should log error', async () => {
      await tryCatchAsync(
        async () => {
          throw new Error('logged error');
        },
        { context: 'TestContext' },
      );
      expect(consoleWarnSpy).toHaveBeenCalledWith(expect.any(String), '[TestContext] logged error');
    });
  });

  describe('isErrorType', () => {
    it('should return true for matching error name', () => {
      const error = new TypeError('type error');
      expect(isErrorType(error, 'TypeError')).toBe(true);
    });

    it('should return false for non-matching error name', () => {
      const error = new Error('generic error');
      expect(isErrorType(error, 'TypeError')).toBe(false);
    });

    it('should return false for non-Error values', () => {
      expect(isErrorType('string', 'Error')).toBe(false);
      expect(isErrorType(null, 'Error')).toBe(false);
      expect(isErrorType({}, 'Error')).toBe(false);
    });

    it('should work with custom error names', () => {
      const error = new Error('custom');
      error.name = 'CustomError';
      expect(isErrorType(error, 'CustomError')).toBe(true);
    });
  });

  describe('isAbortError', () => {
    it('should return true for AbortError', () => {
      const error = new Error('aborted');
      error.name = 'AbortError';
      expect(isAbortError(error)).toBe(true);
    });

    it('should return false for other errors', () => {
      expect(isAbortError(new Error('not abort'))).toBe(false);
      expect(isAbortError(new TypeError('type'))).toBe(false);
    });

    it('should return false for non-Error values', () => {
      expect(isAbortError('AbortError')).toBe(false);
      expect(isAbortError(null)).toBe(false);
    });
  });

  describe('isNetworkError', () => {
    it('should return true for network-related error messages', () => {
      expect(isNetworkError(new Error('Network request failed'))).toBe(true);
      expect(isNetworkError(new Error('Failed to fetch'))).toBe(true);
      expect(isNetworkError(new Error('NetworkError when fetching'))).toBe(true);
      expect(isNetworkError(new Error('Connection refused'))).toBe(true);
      expect(isNetworkError(new Error('User is offline'))).toBe(true);
      expect(isNetworkError(new Error('Request timeout'))).toBe(false);
    });

    it('should be case-insensitive', () => {
      expect(isNetworkError(new Error('NETWORK ERROR'))).toBe(true);
      expect(isNetworkError(new Error('FAILED TO FETCH'))).toBe(true);
    });

    it('should return false for non-network errors', () => {
      expect(isNetworkError(new Error('Invalid input'))).toBe(false);
      expect(isNetworkError(new Error('Not found'))).toBe(false);
      expect(isNetworkError(new Error('Permission denied'))).toBe(false);
    });

    it('should return false for non-Error values', () => {
      expect(isNetworkError('network error')).toBe(false);
      expect(isNetworkError(null)).toBe(false);
      expect(isNetworkError({ message: 'network' })).toBe(false);
    });
  });
});
