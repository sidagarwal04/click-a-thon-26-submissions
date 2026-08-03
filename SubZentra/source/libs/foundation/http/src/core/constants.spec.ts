/**
 * HTTP Constants Tests
 *
 * Validates constant values, structure, and immutability.
 */

import { describe, expect, it } from 'vitest';

import {
  AXIOS_ERROR_CODE,
  CLIENT_HEADERS,
  CONTENT_TYPES,
  DEFAULT_AUTH_CONFIG,
  DEFAULT_HTTP_CIRCUIT_BREAKER_CONFIG,
  DEFAULT_HTTP_RETRY_CONFIG,
  DEFAULT_TIMEOUT_MS,
  DOWNLOAD_TIMEOUT_MS,
  HTTP_ERROR_CODE,
  HTTP_HEADERS,
  HTTP_STATUS,
  PARAMS_ARRAY_FORMAT,
  SERIALIZATION_OPERATION,
  UPLOAD_TIMEOUT_MS,
} from './constants';

describe('HTTP constants', () => {
  // ---------------------------------------------------------------------------
  // Timeouts
  // ---------------------------------------------------------------------------

  describe('timeouts', () => {
    it('should define default timeout as 30 seconds', () => {
      expect(DEFAULT_TIMEOUT_MS).toBe(30_000);
    });

    it('should define upload timeout as 5 minutes', () => {
      expect(UPLOAD_TIMEOUT_MS).toBe(300_000);
    });

    it('should define download timeout as 10 minutes', () => {
      expect(DOWNLOAD_TIMEOUT_MS).toBe(600_000);
    });
  });

  // ---------------------------------------------------------------------------
  // Retry config
  // ---------------------------------------------------------------------------

  describe('DEFAULT_HTTP_RETRY_CONFIG', () => {
    it('should have expected defaults', () => {
      expect(DEFAULT_HTTP_RETRY_CONFIG.enabled).toBe(true);
      expect(DEFAULT_HTTP_RETRY_CONFIG.maxRetries).toBe(3);
      expect(DEFAULT_HTTP_RETRY_CONFIG.initialDelayMs).toBe(1000);
      expect(DEFAULT_HTTP_RETRY_CONFIG.maxDelayMs).toBe(30_000);
      expect(DEFAULT_HTTP_RETRY_CONFIG.backoffMultiplier).toBe(2);
      expect(DEFAULT_HTTP_RETRY_CONFIG.retryableStatusCodes).toEqual([
        408, 429, 500, 502, 503, 504,
      ]);
      expect(DEFAULT_HTTP_RETRY_CONFIG.retryOnNetworkError).toBe(true);
    });

    it('should be frozen', () => {
      expect(Object.isFrozen(DEFAULT_HTTP_RETRY_CONFIG)).toBe(true);
    });
  });

  // ---------------------------------------------------------------------------
  // Circuit breaker config
  // ---------------------------------------------------------------------------

  describe('DEFAULT_HTTP_CIRCUIT_BREAKER_CONFIG', () => {
    it('should have expected defaults', () => {
      expect(DEFAULT_HTTP_CIRCUIT_BREAKER_CONFIG.enabled).toBe(false);
      expect(DEFAULT_HTTP_CIRCUIT_BREAKER_CONFIG.failureThreshold).toBe(5);
      expect(DEFAULT_HTTP_CIRCUIT_BREAKER_CONFIG.resetTimeoutMs).toBe(30_000);
      expect(DEFAULT_HTTP_CIRCUIT_BREAKER_CONFIG.halfOpenMaxRequests).toBe(1);
      expect(DEFAULT_HTTP_CIRCUIT_BREAKER_CONFIG.failureStatusCodes).toEqual([500, 502, 503, 504]);
      expect(DEFAULT_HTTP_CIRCUIT_BREAKER_CONFIG.countNetworkErrors).toBe(true);
      expect(DEFAULT_HTTP_CIRCUIT_BREAKER_CONFIG.maxHosts).toBe(250);
      expect(DEFAULT_HTTP_CIRCUIT_BREAKER_CONFIG.hostTtlMs).toBe(600_000);
      expect(DEFAULT_HTTP_CIRCUIT_BREAKER_CONFIG.debug).toBe(false);
    });

    it('should be frozen', () => {
      expect(Object.isFrozen(DEFAULT_HTTP_CIRCUIT_BREAKER_CONFIG)).toBe(true);
    });
  });

  // ---------------------------------------------------------------------------
  // Auth config
  // ---------------------------------------------------------------------------

  describe('DEFAULT_AUTH_CONFIG', () => {
    it('should default to disabled with Bearer tokens', () => {
      expect(DEFAULT_AUTH_CONFIG.enabled).toBe(false);
      expect(DEFAULT_AUTH_CONFIG.tokenType).toBe('Bearer');
    });

    it('should be frozen', () => {
      expect(Object.isFrozen(DEFAULT_AUTH_CONFIG)).toBe(true);
    });
  });

  // ---------------------------------------------------------------------------
  // Headers
  // ---------------------------------------------------------------------------

  describe('headers', () => {
    it('should define standard HTTP headers', () => {
      expect(HTTP_HEADERS.AUTHORIZATION).toBe('Authorization');
      expect(HTTP_HEADERS.CONTENT_TYPE).toBe('Content-Type');
      expect(HTTP_HEADERS.ACCEPT).toBe('Accept');
      expect(HTTP_HEADERS.X_REQUEST_ID).toBe('X-Request-ID');
    });

    it('should define client headers', () => {
      expect(CLIENT_HEADERS.X_CLIENT_ID).toBe('X-Client-ID');
      expect(CLIENT_HEADERS.X_CLIENT_VERSION).toBe('X-Client-Version');
    });
  });

  // ---------------------------------------------------------------------------
  // Content types
  // ---------------------------------------------------------------------------

  describe('CONTENT_TYPES', () => {
    it('should define common content types', () => {
      expect(CONTENT_TYPES.JSON).toBe('application/json');
      expect(CONTENT_TYPES.FORM_DATA).toBe('multipart/form-data');
      expect(CONTENT_TYPES.OCTET_STREAM).toBe('application/octet-stream');
    });
  });

  // ---------------------------------------------------------------------------
  // HTTP status codes
  // ---------------------------------------------------------------------------

  describe('HTTP_STATUS', () => {
    it('should define success codes', () => {
      expect(HTTP_STATUS.OK).toBe(200);
      expect(HTTP_STATUS.CREATED).toBe(201);
      expect(HTTP_STATUS.NO_CONTENT).toBe(204);
    });

    it('should define client error codes', () => {
      expect(HTTP_STATUS.BAD_REQUEST).toBe(400);
      expect(HTTP_STATUS.UNAUTHORIZED).toBe(401);
      expect(HTTP_STATUS.FORBIDDEN).toBe(403);
      expect(HTTP_STATUS.NOT_FOUND).toBe(404);
      expect(HTTP_STATUS.TOO_MANY_REQUESTS).toBe(429);
    });

    it('should define server error codes', () => {
      expect(HTTP_STATUS.INTERNAL_SERVER_ERROR).toBe(500);
      expect(HTTP_STATUS.BAD_GATEWAY).toBe(502);
      expect(HTTP_STATUS.SERVICE_UNAVAILABLE).toBe(503);
      expect(HTTP_STATUS.GATEWAY_TIMEOUT).toBe(504);
    });

    it('should have exactly 20 status codes', () => {
      expect(Object.keys(HTTP_STATUS)).toHaveLength(20);
    });
  });

  // ---------------------------------------------------------------------------
  // Error codes
  // ---------------------------------------------------------------------------

  describe('HTTP_ERROR_CODE', () => {
    it('should prefix all codes with HTTP_', () => {
      for (const value of Object.values(HTTP_ERROR_CODE)) {
        expect(value).toMatch(/^HTTP_/);
      }
    });

    it('should have exactly 11 error codes', () => {
      expect(Object.keys(HTTP_ERROR_CODE)).toHaveLength(11);
    });
  });

  // ---------------------------------------------------------------------------
  // Params formats
  // ---------------------------------------------------------------------------

  describe('PARAMS_ARRAY_FORMAT', () => {
    it('should define all 4 formats', () => {
      expect(PARAMS_ARRAY_FORMAT.BRACKETS).toBe('brackets');
      expect(PARAMS_ARRAY_FORMAT.INDICES).toBe('indices');
      expect(PARAMS_ARRAY_FORMAT.REPEAT).toBe('repeat');
      expect(PARAMS_ARRAY_FORMAT.COMMA).toBe('comma');
    });
  });

  // ---------------------------------------------------------------------------
  // Serialization
  // ---------------------------------------------------------------------------

  describe('SERIALIZATION_OPERATION', () => {
    it('should define request and response', () => {
      expect(SERIALIZATION_OPERATION.REQUEST).toBe('request');
      expect(SERIALIZATION_OPERATION.RESPONSE).toBe('response');
    });
  });

  // ---------------------------------------------------------------------------
  // Axios error codes
  // ---------------------------------------------------------------------------

  describe('AXIOS_ERROR_CODE', () => {
    it('should define axios-internal error codes', () => {
      expect(AXIOS_ERROR_CODE.CANCELLED).toBe('ERR_CANCELED');
      expect(AXIOS_ERROR_CODE.TIMEOUT).toBe('ECONNABORTED');
      expect(AXIOS_ERROR_CODE.NETWORK).toBe('ERR_NETWORK');
    });
  });
});
