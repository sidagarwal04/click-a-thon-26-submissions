/**
 * HTTP Error Classes Tests
 *
 * Tests for all HttpError subclasses — verifying error codes, messages,
 * status codes, and FoundationError integration.
 */

import { describe, expect, it } from 'vitest';

import { FOUNDATION_ERROR_CODE } from '@open-zentra/foundation-data-model';

import { HTTP_ERROR_CODE } from '../core/constants';
import {
  HttpCancelledError,
  HttpConfigError,
  HttpError,
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

// =============================================================================
// Shared assertions
// =============================================================================

const expectHttpError = (error: HttpError, httpCode: string, foundationCode: string) => {
  expect(error).toBeInstanceOf(Error);
  expect(error).toBeInstanceOf(HttpError);
  expect(error.httpCode).toBe(httpCode);
  expect(error.code).toBe(foundationCode);
  expect(error.name).toBe(error.constructor.name);
  expect(error.message).toBeTruthy();
};

// =============================================================================
// Tests
// =============================================================================

describe('HttpError hierarchy', () => {
  // ---------------------------------------------------------------------------
  // HttpNotInitializedError
  // ---------------------------------------------------------------------------

  describe('HttpNotInitializedError', () => {
    it('should set code and httpCode', () => {
      const error = new HttpNotInitializedError();
      expectHttpError(error, HTTP_ERROR_CODE.NOT_INITIALIZED, FOUNDATION_ERROR_CODE.CONFIG_MISSING);
    });

    it('should include operation in message when provided', () => {
      const error = new HttpNotInitializedError('GET /api/users');
      expect(error.message).toContain('GET /api/users');
    });

    it('should produce a valid message without operation', () => {
      const error = new HttpNotInitializedError();
      expect(error.message).toContain('not initialized');
    });

    it('should attach cause when provided', () => {
      const cause = new Error('root cause');
      const error = new HttpNotInitializedError('op', cause);
      expect(error.cause).toBe(cause);
    });
  });

  // ---------------------------------------------------------------------------
  // HttpConfigError
  // ---------------------------------------------------------------------------

  describe('HttpConfigError', () => {
    it('should set code and httpCode', () => {
      const error = new HttpConfigError('bad base URL');
      expectHttpError(error, HTTP_ERROR_CODE.CONFIG_ERROR, FOUNDATION_ERROR_CODE.CONFIG_INVALID);
    });

    it('should include reason in message', () => {
      const error = new HttpConfigError('missing baseURL');
      expect(error.message).toContain('missing baseURL');
    });
  });

  // ---------------------------------------------------------------------------
  // HttpRequestError
  // ---------------------------------------------------------------------------

  describe('HttpRequestError', () => {
    it('should set code and httpCode', () => {
      const error = new HttpRequestError('Bad request', 400, '/api', 'POST');
      expectHttpError(
        error,
        HTTP_ERROR_CODE.REQUEST_FAILED,
        FOUNDATION_ERROR_CODE.NETWORK_REQUEST_FAILED,
      );
    });

    it('should store statusCode, url, and method', () => {
      const error = new HttpRequestError('fail', 422, '/api/v1', 'PUT');
      expect(error.statusCode).toBe(422);
      expect(error.url).toBe('/api/v1');
      expect(error.method).toBe('PUT');
    });
  });

  // ---------------------------------------------------------------------------
  // HttpTimeoutError
  // ---------------------------------------------------------------------------

  describe('HttpTimeoutError', () => {
    it('should set code and httpCode', () => {
      const error = new HttpTimeoutError(5000);
      expectHttpError(error, HTTP_ERROR_CODE.TIMEOUT, FOUNDATION_ERROR_CODE.NETWORK_TIMEOUT);
    });

    it('should include timeout in message and timeoutMs property', () => {
      const error = new HttpTimeoutError(10_000, '/slow', 'GET');
      expect(error.message).toContain('10000');
      expect(error.timeoutMs).toBe(10_000);
      expect(error.url).toBe('/slow');
      expect(error.method).toBe('GET');
    });
  });

  // ---------------------------------------------------------------------------
  // HttpNetworkError
  // ---------------------------------------------------------------------------

  describe('HttpNetworkError', () => {
    it('should set code and httpCode', () => {
      const error = new HttpNetworkError();
      expectHttpError(
        error,
        HTTP_ERROR_CODE.NETWORK_ERROR,
        FOUNDATION_ERROR_CODE.NETWORK_REQUEST_FAILED,
      );
    });

    it('should use default message when none provided', () => {
      const error = new HttpNetworkError();
      expect(error.message).toContain('Network error');
    });

    it('should use custom message when provided', () => {
      const error = new HttpNetworkError('DNS lookup failed');
      expect(error.message).toBe('DNS lookup failed');
    });
  });

  // ---------------------------------------------------------------------------
  // HttpCancelledError
  // ---------------------------------------------------------------------------

  describe('HttpCancelledError', () => {
    it('should set code and httpCode', () => {
      const error = new HttpCancelledError();
      expectHttpError(
        error,
        HTTP_ERROR_CODE.CANCELLED,
        FOUNDATION_ERROR_CODE.NETWORK_REQUEST_CANCELLED,
      );
    });

    it('should store url and method', () => {
      const error = new HttpCancelledError('/api/long', 'POST');
      expect(error.url).toBe('/api/long');
      expect(error.method).toBe('POST');
    });
  });

  // ---------------------------------------------------------------------------
  // HttpUnauthorizedError
  // ---------------------------------------------------------------------------

  describe('HttpUnauthorizedError', () => {
    it('should set code, httpCode, and statusCode 401', () => {
      const error = new HttpUnauthorizedError('/protected', 'GET');
      expectHttpError(
        error,
        HTTP_ERROR_CODE.UNAUTHORIZED,
        FOUNDATION_ERROR_CODE.NETWORK_REQUEST_FAILED,
      );
      expect(error.statusCode).toBe(401);
    });
  });

  // ---------------------------------------------------------------------------
  // HttpForbiddenError
  // ---------------------------------------------------------------------------

  describe('HttpForbiddenError', () => {
    it('should set code, httpCode, and statusCode 403', () => {
      const error = new HttpForbiddenError('/admin', 'DELETE');
      expectHttpError(
        error,
        HTTP_ERROR_CODE.FORBIDDEN,
        FOUNDATION_ERROR_CODE.NETWORK_REQUEST_FAILED,
      );
      expect(error.statusCode).toBe(403);
    });
  });

  // ---------------------------------------------------------------------------
  // HttpNotFoundError
  // ---------------------------------------------------------------------------

  describe('HttpNotFoundError', () => {
    it('should set code, httpCode, and statusCode 404', () => {
      const error = new HttpNotFoundError('/missing', 'GET');
      expectHttpError(error, HTTP_ERROR_CODE.NOT_FOUND, FOUNDATION_ERROR_CODE.RESOURCE_NOT_FOUND);
      expect(error.statusCode).toBe(404);
    });
  });

  // ---------------------------------------------------------------------------
  // HttpServerError
  // ---------------------------------------------------------------------------

  describe('HttpServerError', () => {
    it('should set code and httpCode', () => {
      const error = new HttpServerError(500);
      expectHttpError(
        error,
        HTTP_ERROR_CODE.SERVER_ERROR,
        FOUNDATION_ERROR_CODE.NETWORK_REQUEST_FAILED,
      );
    });

    it('should store custom status code', () => {
      const error = new HttpServerError(503, 'Service Unavailable');
      expect(error.statusCode).toBe(503);
      expect(error.message).toBe('Service Unavailable');
    });

    it('should use default message when none provided', () => {
      const error = new HttpServerError(502);
      expect(error.message).toContain('502');
    });
  });

  // ---------------------------------------------------------------------------
  // HttpSerializationError
  // ---------------------------------------------------------------------------

  describe('HttpSerializationError', () => {
    it('should set code and httpCode for request serialization', () => {
      const error = new HttpSerializationError('request');
      expectHttpError(
        error,
        HTTP_ERROR_CODE.SERIALIZATION_ERROR,
        FOUNDATION_ERROR_CODE.VALIDATION_FAILED,
      );
      expect(error.message).toContain('request');
    });

    it('should set code and httpCode for response serialization', () => {
      const error = new HttpSerializationError('response');
      expect(error.message).toContain('response');
    });
  });

  // ---------------------------------------------------------------------------
  // Serialization
  // ---------------------------------------------------------------------------

  describe('serialization', () => {
    it('should serialize to JSON via toJSON()', () => {
      const error = new HttpRequestError('Bad Request', 400, '/api', 'POST');
      const json = error.toJSON();
      expect(json.name).toBe('HttpRequestError');
      expect(json.code).toBe(FOUNDATION_ERROR_CODE.NETWORK_REQUEST_FAILED);
      expect(json.message).toBe('Bad Request');
      expect(json.context).toHaveProperty('statusCode', 400);
      expect(json.context).toHaveProperty('url', '/api');
      expect(json.context).toHaveProperty('method', 'POST');
    });

    it('should include cause in serialization', () => {
      const cause = new Error('root');
      const error = new HttpNetworkError('fail', '/url', 'GET', cause);
      const json = error.toJSON();
      expect(json.cause).toBeDefined();
      expect(json.cause?.name).toBe('Error');
      expect(json.cause?.message).toBe('root');
    });
  });
});
