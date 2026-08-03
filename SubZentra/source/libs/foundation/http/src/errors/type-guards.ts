/**
 * HTTP Error Type Guards
 *
 * Type guard functions for identifying and classifying HTTP errors.
 * Only exposes HttpError-based guards — Axios internals are not leaked.
 *
 * @module errors/type-guards
 */

import { HTTP_ERROR_CODE, type HttpErrorCode } from '../core/constants';
import type {
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
import { HttpError } from './http-errors';

const isErrorLike = (value: unknown): value is { message: string; name?: string } =>
  typeof value === 'object' &&
  value !== null &&
  'message' in value &&
  typeof (value as { message: unknown }).message === 'string';

// =============================================================================
// Core Type Guards
// =============================================================================

/**
 * Check if an error is any HttpError.
 *
 * Uses `instanceof` as the fast path; falls back to structural duck-type
 * checking for `httpCode` so that errors crossing realm boundaries (e.g.
 * from Web Workers) are still detected.
 */
export const isHttpError = (error: unknown): error is HttpError =>
  error instanceof HttpError || (isErrorLike(error) && 'httpCode' in error && 'code' in error);

/** Check if an error has a specific HTTP error code */
export const hasHttpErrorCode = (error: unknown, httpCode: HttpErrorCode): error is HttpError =>
  isHttpError(error) && error.httpCode === httpCode;

// =============================================================================
// Specific Error Type Guards
// =============================================================================

/** Check if error is HttpNotInitializedError */
export const isHttpNotInitializedError = (error: unknown): error is HttpNotInitializedError =>
  hasHttpErrorCode(error, HTTP_ERROR_CODE.NOT_INITIALIZED);

/** Check if error is HttpRequestError */
export const isHttpRequestError = (error: unknown): error is HttpRequestError =>
  hasHttpErrorCode(error, HTTP_ERROR_CODE.REQUEST_FAILED);

/** Check if error is HttpTimeoutError */
export const isHttpTimeoutError = (error: unknown): error is HttpTimeoutError =>
  hasHttpErrorCode(error, HTTP_ERROR_CODE.TIMEOUT);

/** Check if error is HttpNetworkError */
export const isHttpNetworkError = (error: unknown): error is HttpNetworkError =>
  hasHttpErrorCode(error, HTTP_ERROR_CODE.NETWORK_ERROR);

/** Check if error is HttpCancelledError */
export const isHttpCancelledError = (error: unknown): error is HttpCancelledError =>
  hasHttpErrorCode(error, HTTP_ERROR_CODE.CANCELLED);

/** Check if error is HttpUnauthorizedError */
export const isHttpUnauthorizedError = (error: unknown): error is HttpUnauthorizedError =>
  hasHttpErrorCode(error, HTTP_ERROR_CODE.UNAUTHORIZED);

/** Check if error is HttpForbiddenError */
export const isHttpForbiddenError = (error: unknown): error is HttpForbiddenError =>
  hasHttpErrorCode(error, HTTP_ERROR_CODE.FORBIDDEN);

/** Check if error is HttpNotFoundError */
export const isHttpNotFoundError = (error: unknown): error is HttpNotFoundError =>
  hasHttpErrorCode(error, HTTP_ERROR_CODE.NOT_FOUND);

/** Check if error is HttpServerError */
export const isHttpServerError = (error: unknown): error is HttpServerError =>
  hasHttpErrorCode(error, HTTP_ERROR_CODE.SERVER_ERROR);

/** Check if error is HttpConfigError */
export const isHttpConfigError = (error: unknown): error is HttpConfigError =>
  hasHttpErrorCode(error, HTTP_ERROR_CODE.CONFIG_ERROR);

/** Check if error is HttpSerializationError */
export const isHttpSerializationError = (error: unknown): error is HttpSerializationError =>
  hasHttpErrorCode(error, HTTP_ERROR_CODE.SERIALIZATION_ERROR);

// =============================================================================
// Category Type Guards
// =============================================================================

/** Check if error is an authentication error (401 or 403) */
export const isAuthenticationError = (error: unknown): error is HttpError =>
  isHttpUnauthorizedError(error) || isHttpForbiddenError(error);

/** Check if error is a client error (4xx status code) */
export const isClientError = (error: unknown): boolean =>
  isHttpError(error) &&
  error.statusCode !== undefined &&
  error.statusCode >= 400 &&
  error.statusCode < 500;

/** Check if error is a server error (5xx status code) */
export const isServerError = (error: unknown): boolean =>
  isHttpServerError(error) ||
  (isHttpError(error) &&
    error.statusCode !== undefined &&
    error.statusCode >= 500 &&
    error.statusCode < 600);

/**
 * Check if an HTTP error is retryable.
 *
 * Retryable errors:
 * - Network errors (transient connectivity issues)
 * - Timeout errors
 * - 5xx server errors
 * - 408 Request Timeout
 * - 429 Too Many Requests
 */
export const isRetryableHttpError = (error: unknown): boolean => {
  if (isHttpNetworkError(error) || isHttpTimeoutError(error)) {
    return true;
  }

  if (isHttpError(error) && error.statusCode !== undefined) {
    return error.statusCode >= 500 || error.statusCode === 408 || error.statusCode === 429;
  }

  return false;
};

/**
 * Check if an HTTP error should NOT be retried.
 *
 * Non-retryable errors:
 * - Cancelled requests (explicit user/system action)
 * - 4xx client errors (except 408 Request Timeout, 429 Too Many Requests)
 */
export const isNonRetryableHttpError = (error: unknown): boolean => {
  if (isHttpCancelledError(error)) {
    return true;
  }

  if (isHttpError(error) && error.statusCode !== undefined) {
    return (
      error.statusCode >= 400 &&
      error.statusCode < 500 &&
      error.statusCode !== 408 &&
      error.statusCode !== 429
    );
  }

  return false;
};
