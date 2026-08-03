/**
 * Tests for error guard utilities
 */

import { describe, expect, it } from 'vitest';

import {
  hasErrorCode,
  isAbortError,
  isErrorType,
  isNetworkError,
  isRangeError,
  isRetriableHttpStatus,
  isSyntaxError,
  isTimeoutError,
  isTypeError,
} from './error-guards';

describe('isErrorType', () => {
  it('should return true for matching error name', () => {
    const error = new Error('test');
    error.name = 'CustomError';

    expect(isErrorType(error, 'CustomError')).toBe(true);
  });

  it('should return false for non-matching error name', () => {
    const error = new Error('test');

    expect(isErrorType(error, 'CustomError')).toBe(false);
  });

  it('should return false for non-Error values', () => {
    expect(isErrorType('error', 'Error')).toBe(false);
    expect(isErrorType(null, 'Error')).toBe(false);
    expect(isErrorType({}, 'Error')).toBe(false);
  });
});

describe('isAbortError', () => {
  it('should return true for AbortError', () => {
    const error = new Error('Aborted');
    error.name = 'AbortError';

    expect(isAbortError(error)).toBe(true);
  });

  it('should return false for other errors', () => {
    expect(isAbortError(new Error('test'))).toBe(false);
    expect(isAbortError(new TypeError('test'))).toBe(false);
  });
});

describe('isNetworkError', () => {
  it('should detect network-related errors', () => {
    expect(isNetworkError(new Error('Network error'))).toBe(true);
    expect(isNetworkError(new Error('Failed to fetch'))).toBe(true);
    expect(isNetworkError(new Error('Connection refused'))).toBe(true);
    expect(isNetworkError(new Error('ECONNREFUSED'))).toBe(true);
    expect(isNetworkError(new Error('offline'))).toBe(true);
  });

  it('should return false for timeout errors (handled by isTimeoutError)', () => {
    expect(isNetworkError(new Error('Request timeout'))).toBe(false);
  });

  it('should return false for non-network errors', () => {
    expect(isNetworkError(new Error('Invalid argument'))).toBe(false);
    expect(isNetworkError(new Error('Permission denied'))).toBe(false);
  });

  it('should return false for non-Error values', () => {
    expect(isNetworkError('network error')).toBe(false);
    expect(isNetworkError(null)).toBe(false);
  });
});

describe('isTimeoutError', () => {
  it('should detect timeout errors', () => {
    expect(isTimeoutError(new Error('Request timed out'))).toBe(true);
    expect(isTimeoutError(new Error('Operation timeout'))).toBe(true);

    const timeoutError = new Error('Timeout');
    timeoutError.name = 'TimeoutError';
    expect(isTimeoutError(timeoutError)).toBe(true);
  });

  it('should return false for non-timeout errors', () => {
    expect(isTimeoutError(new Error('Unknown error'))).toBe(false);
  });
});

describe('isTypeError', () => {
  it('should return true for TypeError', () => {
    expect(isTypeError(new TypeError('test'))).toBe(true);
  });

  it('should return false for other errors', () => {
    expect(isTypeError(new Error('test'))).toBe(false);
    expect(isTypeError(new SyntaxError('test'))).toBe(false);
  });
});

describe('isSyntaxError', () => {
  it('should return true for SyntaxError', () => {
    expect(isSyntaxError(new SyntaxError('test'))).toBe(true);
  });

  it('should return false for other errors', () => {
    expect(isSyntaxError(new Error('test'))).toBe(false);
    expect(isSyntaxError(new TypeError('test'))).toBe(false);
  });
});

describe('isRangeError', () => {
  it('should return true for RangeError', () => {
    expect(isRangeError(new RangeError('test'))).toBe(true);
  });

  it('should return false for other errors', () => {
    expect(isRangeError(new Error('test'))).toBe(false);
  });
});

describe('hasErrorCode', () => {
  it('should return true for matching string code', () => {
    const error = new Error('test') as Error & { code: string };
    error.code = 'ENOENT';

    expect(hasErrorCode(error, 'ENOENT')).toBe(true);
  });

  it('should return true for matching number code', () => {
    const error = new Error('test') as Error & { code: number };
    error.code = 404;

    expect(hasErrorCode(error, 404)).toBe(true);
  });

  it('should return false for non-matching code', () => {
    const error = new Error('test') as Error & { code: string };
    error.code = 'ENOENT';

    expect(hasErrorCode(error, 'EPERM')).toBe(false);
  });

  it('should return false for errors without code', () => {
    expect(hasErrorCode(new Error('test'), 'ENOENT')).toBe(false);
  });
});

describe('isRetriableHttpStatus', () => {
  it('should return true for server errors (5xx)', () => {
    expect(isRetriableHttpStatus(500)).toBe(true);
    expect(isRetriableHttpStatus(502)).toBe(true);
    expect(isRetriableHttpStatus(503)).toBe(true);
    expect(isRetriableHttpStatus(504)).toBe(true);
  });

  it('should return true for specific client errors', () => {
    expect(isRetriableHttpStatus(408)).toBe(true); // Request Timeout
    expect(isRetriableHttpStatus(429)).toBe(true); // Too Many Requests
  });

  it('should return true for network error (0)', () => {
    expect(isRetriableHttpStatus(0)).toBe(true);
  });

  it('should return false for success codes', () => {
    expect(isRetriableHttpStatus(200)).toBe(false);
    expect(isRetriableHttpStatus(201)).toBe(false);
    expect(isRetriableHttpStatus(204)).toBe(false);
  });

  it('should return false for non-retriable client errors', () => {
    expect(isRetriableHttpStatus(400)).toBe(false);
    expect(isRetriableHttpStatus(401)).toBe(false);
    expect(isRetriableHttpStatus(403)).toBe(false);
    expect(isRetriableHttpStatus(404)).toBe(false);
  });
});
