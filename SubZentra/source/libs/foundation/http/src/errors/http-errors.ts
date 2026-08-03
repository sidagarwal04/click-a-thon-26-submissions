/**
 * HTTP Error Classes
 *
 * Custom error classes for HTTP operations.
 * All errors extend FoundationError from data-model with proper
 * FoundationErrorCode mapping per error type.
 *
 * @module errors/http-errors
 */

import {
  FOUNDATION_ERROR_CODE,
  FoundationError,
  type ErrorContext,
  type HttpMethod,
} from '@open-zentra/foundation-data-model';

import {
  HTTP_ERROR_CODE,
  type HttpErrorCode,
  type SerializationOperation,
} from '../core/constants';

// =============================================================================
// HTTP Error Options
// =============================================================================

interface HttpErrorOptions {
  readonly statusCode?: number;
  readonly url?: string;
  readonly method?: HttpMethod;
  readonly context?: ErrorContext;
  readonly cause?: Error;
}

// =============================================================================
// Base HTTP Error
// =============================================================================

/**
 * Abstract base class for all HTTP errors.
 *
 * Each concrete subclass maps to a specific FoundationErrorCode for proper
 * categorization while also carrying an HTTP-specific httpCode for granular
 * identification within the HTTP domain.
 */
export abstract class HttpError extends FoundationError {
  /** HTTP-specific error code for granular identification */
  abstract readonly httpCode: HttpErrorCode;

  /** HTTP status code from the response (when available) */
  readonly statusCode?: number;

  /** Request URL */
  readonly url?: string;

  /** HTTP method */
  readonly method?: HttpMethod;

  constructor(message: string, options: HttpErrorOptions = {}) {
    super(
      message,
      {
        ...options.context,
        domain: 'http',
        statusCode: options.statusCode,
        url: options.url,
        method: options.method,
      },
      options.cause,
    );
    this.statusCode = options.statusCode;
    this.url = options.url;
    this.method = options.method;
  }
}

// =============================================================================
// Configuration Errors
// =============================================================================

/**
 * Thrown when the HTTP client is accessed before initialization.
 *
 * FoundationErrorCode: CONFIG_MISSING
 */
export class HttpNotInitializedError extends HttpError {
  readonly code = FOUNDATION_ERROR_CODE.CONFIG_MISSING;
  readonly httpCode = HTTP_ERROR_CODE.NOT_INITIALIZED;

  constructor(operation?: string, cause?: Error) {
    super(`HTTP client not initialized${operation ? `. Cannot perform: ${operation}` : ''}`, {
      context: { operation },
      cause,
    });
  }
}

/**
 * Thrown when HTTP configuration is invalid.
 *
 * FoundationErrorCode: CONFIG_INVALID
 */
export class HttpConfigError extends HttpError {
  readonly code = FOUNDATION_ERROR_CODE.CONFIG_INVALID;
  readonly httpCode = HTTP_ERROR_CODE.CONFIG_ERROR;

  constructor(reason: string, cause?: Error) {
    super(`HTTP configuration error: ${reason}`, { context: { reason }, cause });
  }
}

// =============================================================================
// Network / Transport Errors
// =============================================================================

/**
 * Thrown when an HTTP request fails with a non-specific error.
 *
 * FoundationErrorCode: NETWORK_REQUEST_FAILED
 */
export class HttpRequestError extends HttpError {
  readonly code = FOUNDATION_ERROR_CODE.NETWORK_REQUEST_FAILED;
  readonly httpCode = HTTP_ERROR_CODE.REQUEST_FAILED;

  constructor(
    message: string,
    statusCode?: number,
    url?: string,
    method?: HttpMethod,
    cause?: Error,
  ) {
    super(message, { statusCode, url, method, cause });
  }
}

/**
 * Thrown when an HTTP request exceeds its timeout duration.
 *
 * FoundationErrorCode: NETWORK_TIMEOUT
 */
export class HttpTimeoutError extends HttpError {
  readonly code = FOUNDATION_ERROR_CODE.NETWORK_TIMEOUT;
  readonly httpCode = HTTP_ERROR_CODE.TIMEOUT;

  /** Timeout duration in milliseconds */
  readonly timeoutMs: number;

  constructor(timeoutMs: number, url?: string, method?: HttpMethod, cause?: Error) {
    super(`Request timed out after ${timeoutMs}ms`, {
      url,
      method,
      context: { timeoutMs },
      cause,
    });
    this.timeoutMs = timeoutMs;
  }
}

/**
 * Thrown when a network-level error occurs (DNS failure, connection refused, etc.).
 *
 * FoundationErrorCode: NETWORK_REQUEST_FAILED
 */
export class HttpNetworkError extends HttpError {
  readonly code = FOUNDATION_ERROR_CODE.NETWORK_REQUEST_FAILED;
  readonly httpCode = HTTP_ERROR_CODE.NETWORK_ERROR;

  constructor(message?: string, url?: string, method?: HttpMethod, cause?: Error) {
    super(message ?? 'Network error occurred', { url, method, cause });
  }
}

/**
 * Thrown when an HTTP request is explicitly cancelled (e.g. AbortController).
 *
 * FoundationErrorCode: NETWORK_REQUEST_CANCELLED
 */
export class HttpCancelledError extends HttpError {
  readonly code = FOUNDATION_ERROR_CODE.NETWORK_REQUEST_CANCELLED;
  readonly httpCode = HTTP_ERROR_CODE.CANCELLED;

  constructor(url?: string, method?: HttpMethod, cause?: Error) {
    super('Request was cancelled', { url, method, cause });
  }
}

// =============================================================================
// Authentication / Authorization Errors
// =============================================================================

/**
 * Thrown when the server responds with 401 Unauthorized.
 *
 * FoundationErrorCode: NETWORK_REQUEST_FAILED
 */
export class HttpUnauthorizedError extends HttpError {
  readonly code = FOUNDATION_ERROR_CODE.NETWORK_REQUEST_FAILED;
  readonly httpCode = HTTP_ERROR_CODE.UNAUTHORIZED;

  constructor(url?: string, method?: HttpMethod, cause?: Error) {
    super('Unauthorized - authentication required', {
      statusCode: 401,
      url,
      method,
      cause,
    });
  }
}

/**
 * Thrown when the server responds with 403 Forbidden.
 *
 * FoundationErrorCode: NETWORK_REQUEST_FAILED
 */
export class HttpForbiddenError extends HttpError {
  readonly code = FOUNDATION_ERROR_CODE.NETWORK_REQUEST_FAILED;
  readonly httpCode = HTTP_ERROR_CODE.FORBIDDEN;

  constructor(url?: string, method?: HttpMethod, cause?: Error) {
    super('Forbidden - insufficient permissions', {
      statusCode: 403,
      url,
      method,
      cause,
    });
  }
}

// =============================================================================
// Resource Errors
// =============================================================================

/**
 * Thrown when the server responds with 404 Not Found.
 *
 * FoundationErrorCode: RESOURCE_NOT_FOUND
 */
export class HttpNotFoundError extends HttpError {
  readonly code = FOUNDATION_ERROR_CODE.RESOURCE_NOT_FOUND;
  readonly httpCode = HTTP_ERROR_CODE.NOT_FOUND;

  constructor(url?: string, method?: HttpMethod, cause?: Error) {
    super('Resource not found', {
      statusCode: 404,
      url,
      method,
      cause,
    });
  }
}

// =============================================================================
// Server Errors
// =============================================================================

/**
 * Thrown when the server responds with a 5xx status code.
 *
 * FoundationErrorCode: NETWORK_REQUEST_FAILED
 */
export class HttpServerError extends HttpError {
  readonly code = FOUNDATION_ERROR_CODE.NETWORK_REQUEST_FAILED;
  readonly httpCode = HTTP_ERROR_CODE.SERVER_ERROR;

  constructor(
    statusCode: number,
    message?: string,
    url?: string,
    method?: HttpMethod,
    cause?: Error,
  ) {
    super(message ?? `Server error: ${statusCode}`, {
      statusCode,
      url,
      method,
      cause,
    });
  }
}

// =============================================================================
// Serialization Errors
// =============================================================================

/**
 * Thrown when request or response data serialization fails.
 *
 * FoundationErrorCode: VALIDATION_FAILED
 */
export class HttpSerializationError extends HttpError {
  readonly code = FOUNDATION_ERROR_CODE.VALIDATION_FAILED;
  readonly httpCode = HTTP_ERROR_CODE.SERIALIZATION_ERROR;

  constructor(operation: SerializationOperation, cause?: Error) {
    super(`Failed to serialize ${operation} data`, {
      context: { operation },
      cause,
    });
  }
}
