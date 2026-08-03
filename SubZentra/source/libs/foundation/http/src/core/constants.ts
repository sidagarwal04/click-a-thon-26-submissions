/**
 * HTTP Client Constants
 *
 * Default configurations and constants for the foundation-http library.
 * All constants follow CAPITAL_SNAKE_CASE naming convention.
 *
 * @module core/constants
 */

import type { AuthConfig, HttpCircuitBreakerConfig, HttpRetryConfig } from './types';

// =============================================================================
// Timeout Defaults
// =============================================================================

/** Default request timeout in milliseconds (30 seconds) */
export const DEFAULT_TIMEOUT_MS = 30_000;

/** Upload timeout in milliseconds (5 minutes) */
export const UPLOAD_TIMEOUT_MS = 300_000;

/** Download timeout in milliseconds (10 minutes) */
export const DOWNLOAD_TIMEOUT_MS = 600_000;

// =============================================================================
// Retry Defaults
// =============================================================================

/**
 * Default HTTP retry configuration
 *
 * Named DEFAULT_HTTP_RETRY_CONFIG to avoid collision with
 * foundation-utils DEFAULT_RETRY_CONFIG.
 */
export const DEFAULT_HTTP_RETRY_CONFIG: Readonly<HttpRetryConfig> = Object.freeze({
  enabled: true,
  maxRetries: 3,
  initialDelayMs: 1000,
  maxDelayMs: 30_000,
  backoffMultiplier: 2,
  retryableStatusCodes: [408, 429, 500, 502, 503, 504],
  retryOnNetworkError: true,
});

// =============================================================================
// Circuit Breaker Defaults
// =============================================================================

/** Default circuit-breaker configuration */
export const DEFAULT_HTTP_CIRCUIT_BREAKER_CONFIG: Readonly<HttpCircuitBreakerConfig> =
  Object.freeze({
    enabled: false,
    failureThreshold: 5,
    resetTimeoutMs: 30_000,
    halfOpenMaxRequests: 1,
    failureStatusCodes: [500, 502, 503, 504],
    countNetworkErrors: true,
    maxHosts: 250,
    hostTtlMs: 10 * 60_000,
    debug: false,
  });

// =============================================================================
// Auth Defaults
// =============================================================================

/** Default auth configuration */
export const DEFAULT_AUTH_CONFIG: Readonly<AuthConfig> = Object.freeze({
  enabled: false,
  tokenType: 'Bearer',
});

// =============================================================================
// Header Names
// =============================================================================

/** Standard HTTP header names */
export const HTTP_HEADERS = {
  AUTHORIZATION: 'Authorization',
  CONTENT_TYPE: 'Content-Type',
  ACCEPT: 'Accept',
  X_REQUEST_ID: 'X-Request-ID',
  X_CORRELATION_ID: 'X-Correlation-ID',
} as const;

/** Custom client identification headers */
export const CLIENT_HEADERS = {
  X_CLIENT_ID: 'X-Client-ID',
  X_CLIENT_VERSION: 'X-Client-Version',
  X_CLIENT_PLATFORM: 'X-Client-Platform',
  X_CLIENT_SESSION_ID: 'X-Client-Session-ID',
} as const;

// =============================================================================
// Content Types
// =============================================================================

/** Common content type values */
export const CONTENT_TYPES = {
  JSON: 'application/json',
  FORM_DATA: 'multipart/form-data',
  FORM_URLENCODED: 'application/x-www-form-urlencoded',
  TEXT: 'text/plain',
  HTML: 'text/html',
  OCTET_STREAM: 'application/octet-stream',
} as const;

// =============================================================================
// HTTP Status Codes
// =============================================================================

/** HTTP status codes */
export const HTTP_STATUS = {
  OK: 200,
  CREATED: 201,
  ACCEPTED: 202,
  NO_CONTENT: 204,
  MOVED_PERMANENTLY: 301,
  FOUND: 302,
  NOT_MODIFIED: 304,
  BAD_REQUEST: 400,
  UNAUTHORIZED: 401,
  FORBIDDEN: 403,
  NOT_FOUND: 404,
  METHOD_NOT_ALLOWED: 405,
  CONFLICT: 409,
  GONE: 410,
  UNPROCESSABLE_ENTITY: 422,
  TOO_MANY_REQUESTS: 429,
  INTERNAL_SERVER_ERROR: 500,
  BAD_GATEWAY: 502,
  SERVICE_UNAVAILABLE: 503,
  GATEWAY_TIMEOUT: 504,
} as const;

// =============================================================================
// Error Codes
// =============================================================================

/** HTTP-specific error codes */
export const HTTP_ERROR_CODE = {
  NOT_INITIALIZED: 'HTTP_NOT_INITIALIZED',
  REQUEST_FAILED: 'HTTP_REQUEST_FAILED',
  TIMEOUT: 'HTTP_TIMEOUT',
  NETWORK_ERROR: 'HTTP_NETWORK_ERROR',
  CANCELLED: 'HTTP_CANCELLED',
  UNAUTHORIZED: 'HTTP_UNAUTHORIZED',
  FORBIDDEN: 'HTTP_FORBIDDEN',
  NOT_FOUND: 'HTTP_NOT_FOUND',
  SERVER_ERROR: 'HTTP_SERVER_ERROR',
  CONFIG_ERROR: 'HTTP_CONFIG_ERROR',
  SERIALIZATION_ERROR: 'HTTP_SERIALIZATION_ERROR',
} as const;

export type HttpErrorCode = (typeof HTTP_ERROR_CODE)[keyof typeof HTTP_ERROR_CODE];

// =============================================================================
// Params Array Format
// =============================================================================

/** Query parameter array serialization formats */
export const PARAMS_ARRAY_FORMAT = {
  BRACKETS: 'brackets',
  INDICES: 'indices',
  REPEAT: 'repeat',
  COMMA: 'comma',
} as const;

export type ParamsArrayFormat = (typeof PARAMS_ARRAY_FORMAT)[keyof typeof PARAMS_ARRAY_FORMAT];

// =============================================================================
// Serialization Operation
// =============================================================================

/** Serialization operation direction */
export const SERIALIZATION_OPERATION = {
  REQUEST: 'request',
  RESPONSE: 'response',
} as const;

export type SerializationOperation =
  (typeof SERIALIZATION_OPERATION)[keyof typeof SERIALIZATION_OPERATION];

// =============================================================================
// Axios Error Codes (for internal matching)
// =============================================================================

/** Axios internal error codes used for error classification */
export const AXIOS_ERROR_CODE = {
  CANCELLED: 'ERR_CANCELED',
  TIMEOUT: 'ECONNABORTED',
  TIMEOUT_ALT: 'ETIMEDOUT',
  NETWORK: 'ERR_NETWORK',
} as const;
