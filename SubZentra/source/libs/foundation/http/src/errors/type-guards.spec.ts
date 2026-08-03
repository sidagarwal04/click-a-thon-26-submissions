/**
 * HTTP Error Type Guards Tests
 *
 * Tests for type guard functions that classify HTTP errors.
 */

import { describe, expect, it } from 'vitest';

import { HTTP_ERROR_CODE } from '../core/constants';
import {
  HttpCancelledError,
  HttpConfigError,
  HttpForbiddenError,
  HttpNetworkError,
  HttpNotFoundError,
  HttpNotInitializedError,
  HttpRequestError,
  HttpSerializationError,
  HttpServerError,
  HttpTimeoutError,
  HttpUnauthorizedError,
} from './http-errors';
import {
  hasHttpErrorCode,
  isAuthenticationError,
  isClientError,
  isHttpCancelledError,
  isHttpConfigError,
  isHttpError,
  isHttpForbiddenError,
  isHttpNetworkError,
  isHttpNotFoundError,
  isHttpNotInitializedError,
  isHttpRequestError,
  isHttpSerializationError,
  isHttpServerError,
  isHttpTimeoutError,
  isHttpUnauthorizedError,
  isNonRetryableHttpError,
  isRetryableHttpError,
  isServerError,
} from './type-guards';

// =============================================================================
// Core type guards
// =============================================================================

describe('isHttpError', () => {
  it('should return true for HttpError instances', () => {
    expect(isHttpError(new HttpRequestError('fail', 400))).toBe(true);
    expect(isHttpError(new HttpTimeoutError(1000))).toBe(true);
    expect(isHttpError(new HttpNetworkError())).toBe(true);
  });

  it('should return false for non-HttpError values', () => {
    expect(isHttpError(null)).toBe(false);
    expect(isHttpError(undefined)).toBe(false);
    expect(isHttpError('string')).toBe(false);
    expect(isHttpError(new Error('plain'))).toBe(false);
    expect(isHttpError(42)).toBe(false);
  });

  it('should detect structural duck-type errors (cross-realm)', () => {
    const fakeHttpError = {
      httpCode: HTTP_ERROR_CODE.REQUEST_FAILED,
      code: 'NETWORK_REQUEST_FAILED',
      message: 'fail',
      name: 'HttpRequestError',
    };
    expect(isHttpError(fakeHttpError)).toBe(true);
  });

  it('should reject partial structural matches', () => {
    expect(isHttpError({ httpCode: 'x' })).toBe(false);
    expect(isHttpError({ code: 'x', message: 'y' })).toBe(false);
  });
});

describe('hasHttpErrorCode', () => {
  it('should match specific HTTP error codes', () => {
    const error = new HttpTimeoutError(5000);
    expect(hasHttpErrorCode(error, HTTP_ERROR_CODE.TIMEOUT)).toBe(true);
    expect(hasHttpErrorCode(error, HTTP_ERROR_CODE.NETWORK_ERROR)).toBe(false);
  });
});

// =============================================================================
// Specific type guards
// =============================================================================

describe('specific type guards', () => {
  it('isHttpNotInitializedError', () => {
    expect(isHttpNotInitializedError(new HttpNotInitializedError())).toBe(true);
    expect(isHttpNotInitializedError(new HttpNetworkError())).toBe(false);
  });

  it('isHttpRequestError', () => {
    expect(isHttpRequestError(new HttpRequestError('fail', 400))).toBe(true);
    expect(isHttpRequestError(new HttpTimeoutError(1000))).toBe(false);
  });

  it('isHttpTimeoutError', () => {
    expect(isHttpTimeoutError(new HttpTimeoutError(1000))).toBe(true);
    expect(isHttpTimeoutError(new HttpNetworkError())).toBe(false);
  });

  it('isHttpNetworkError', () => {
    expect(isHttpNetworkError(new HttpNetworkError())).toBe(true);
    expect(isHttpNetworkError(new HttpTimeoutError(1000))).toBe(false);
  });

  it('isHttpCancelledError', () => {
    expect(isHttpCancelledError(new HttpCancelledError())).toBe(true);
    expect(isHttpCancelledError(new HttpNetworkError())).toBe(false);
  });

  it('isHttpUnauthorizedError', () => {
    expect(isHttpUnauthorizedError(new HttpUnauthorizedError())).toBe(true);
    expect(isHttpUnauthorizedError(new HttpForbiddenError())).toBe(false);
  });

  it('isHttpForbiddenError', () => {
    expect(isHttpForbiddenError(new HttpForbiddenError())).toBe(true);
    expect(isHttpForbiddenError(new HttpUnauthorizedError())).toBe(false);
  });

  it('isHttpNotFoundError', () => {
    expect(isHttpNotFoundError(new HttpNotFoundError())).toBe(true);
    expect(isHttpNotFoundError(new HttpServerError(500))).toBe(false);
  });

  it('isHttpServerError', () => {
    expect(isHttpServerError(new HttpServerError(500))).toBe(true);
    expect(isHttpServerError(new HttpNotFoundError())).toBe(false);
  });

  it('isHttpConfigError', () => {
    expect(isHttpConfigError(new HttpConfigError('bad'))).toBe(true);
    expect(isHttpConfigError(new HttpNetworkError())).toBe(false);
  });

  it('isHttpSerializationError', () => {
    expect(isHttpSerializationError(new HttpSerializationError('request'))).toBe(true);
    expect(isHttpSerializationError(new HttpNetworkError())).toBe(false);
  });
});

// =============================================================================
// Category type guards
// =============================================================================

describe('category type guards', () => {
  describe('isAuthenticationError', () => {
    it('should match 401 and 403', () => {
      expect(isAuthenticationError(new HttpUnauthorizedError())).toBe(true);
      expect(isAuthenticationError(new HttpForbiddenError())).toBe(true);
    });

    it('should not match other errors', () => {
      expect(isAuthenticationError(new HttpNotFoundError())).toBe(false);
      expect(isAuthenticationError(new HttpServerError(500))).toBe(false);
    });
  });

  describe('isClientError', () => {
    it('should match 4xx errors', () => {
      expect(isClientError(new HttpUnauthorizedError())).toBe(true);
      expect(isClientError(new HttpForbiddenError())).toBe(true);
      expect(isClientError(new HttpNotFoundError())).toBe(true);
      expect(isClientError(new HttpRequestError('bad', 422))).toBe(true);
    });

    it('should not match 5xx errors', () => {
      expect(isClientError(new HttpServerError(500))).toBe(false);
    });
  });

  describe('isServerError', () => {
    it('should match 5xx errors', () => {
      expect(isServerError(new HttpServerError(500))).toBe(true);
      expect(isServerError(new HttpServerError(503))).toBe(true);
    });

    it('should not match 4xx errors', () => {
      expect(isServerError(new HttpNotFoundError())).toBe(false);
    });
  });

  describe('isRetryableHttpError', () => {
    it('should mark network and timeout errors as retryable', () => {
      expect(isRetryableHttpError(new HttpNetworkError())).toBe(true);
      expect(isRetryableHttpError(new HttpTimeoutError(5000))).toBe(true);
    });

    it('should mark 5xx errors as retryable', () => {
      expect(isRetryableHttpError(new HttpServerError(500))).toBe(true);
      expect(isRetryableHttpError(new HttpServerError(503))).toBe(true);
    });

    it('should mark 408 and 429 as retryable', () => {
      expect(isRetryableHttpError(new HttpRequestError('timeout', 408))).toBe(true);
      expect(isRetryableHttpError(new HttpRequestError('rate limit', 429))).toBe(true);
    });

    it('should not mark 4xx (non-408/429) as retryable', () => {
      expect(isRetryableHttpError(new HttpNotFoundError())).toBe(false);
      expect(isRetryableHttpError(new HttpUnauthorizedError())).toBe(false);
    });
  });

  describe('isNonRetryableHttpError', () => {
    it('should mark cancelled errors as non-retryable', () => {
      expect(isNonRetryableHttpError(new HttpCancelledError())).toBe(true);
    });

    it('should mark 4xx (non-408/429) as non-retryable', () => {
      expect(isNonRetryableHttpError(new HttpUnauthorizedError())).toBe(true);
      expect(isNonRetryableHttpError(new HttpForbiddenError())).toBe(true);
      expect(isNonRetryableHttpError(new HttpNotFoundError())).toBe(true);
    });

    it('should not mark 408 and 429 as non-retryable', () => {
      expect(isNonRetryableHttpError(new HttpRequestError('timeout', 408))).toBe(false);
      expect(isNonRetryableHttpError(new HttpRequestError('rate limit', 429))).toBe(false);
    });

    it('should not mark 5xx as non-retryable', () => {
      expect(isNonRetryableHttpError(new HttpServerError(500))).toBe(false);
    });
  });
});
