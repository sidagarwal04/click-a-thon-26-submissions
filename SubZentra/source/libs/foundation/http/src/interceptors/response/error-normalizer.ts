/**
 * Error Normalizer Response Interceptor
 *
 * Converts axios errors and non-2xx responses into typed HttpError instances.
 * This interceptor runs LAST in the response chain so that retry and
 * unauthorized-handler can operate on raw responses/AxiosErrors first.
 *
 * @module interceptors/response/error-normalizer
 */

import type { AxiosError, AxiosInstance, AxiosResponse } from 'axios';
import { isAxiosError } from 'axios';

import type { HttpMethod } from '@open-zentra/foundation-data-model';
import { createDebugLogger } from '@open-zentra/foundation-utils';

import { AXIOS_ERROR_CODE, HTTP_STATUS } from '../../core/constants';
import { getRequestMetadata } from '../../core/request-metadata';
import {
  HttpCancelledError,
  HttpForbiddenError,
  HttpNetworkError,
  HttpNotFoundError,
  HttpRequestError,
  HttpServerError,
  HttpTimeoutError,
  HttpUnauthorizedError,
} from '../../errors/http-errors';

// =============================================================================
// Types
// =============================================================================

export interface ErrorNormalizerOptions {
  readonly debug?: boolean;
}

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === 'object' && value !== null;

// =============================================================================
// Shared Status-to-Error Mapping
// =============================================================================

/**
 * Extracts a human-readable error message from an HTTP response body.
 * Supports common API error shapes: `{ message }`, `{ error }`,
 * `{ errorMessage }`, `{ errors: [{ message }] }`.
 */
const extractErrorMessage = (response: AxiosResponse): string | undefined => {
  const data = response.data;

  if (typeof data === 'string') {
    return data;
  }

  if (isRecord(data)) {
    const obj = data;
    if (typeof obj.message === 'string') return obj.message;
    if (typeof obj.error === 'string') return obj.error;
    if (typeof obj.errorMessage === 'string') return obj.errorMessage;
    if (Array.isArray(obj.errors)) {
      const firstError = obj.errors[0];
      if (isRecord(firstError) && typeof firstError.message === 'string') {
        return firstError.message;
      }
    }
  }

  return undefined;
};

/**
 * Maps an HTTP status code to the appropriate HttpError subclass.
 * Used by both the fulfilled (non-2xx response) and rejected (AxiosError with
 * response) code paths to avoid duplicating the switch logic.
 */
const mapStatusToError = (
  status: number,
  message: string,
  url: string | undefined,
  method: HttpMethod | undefined,
  cause?: Error,
): Error => {
  switch (status) {
    case HTTP_STATUS.UNAUTHORIZED:
      return new HttpUnauthorizedError(url, method, cause);
    case HTTP_STATUS.FORBIDDEN:
      return new HttpForbiddenError(url, method, cause);
    case HTTP_STATUS.NOT_FOUND:
      return new HttpNotFoundError(url, method, cause);
    default:
      if (status >= 500) {
        return new HttpServerError(status, message, url, method, cause);
      }
      return new HttpRequestError(message, status, url, method, cause);
  }
};

// =============================================================================
// Conversion Functions
// =============================================================================

/**
 * Converts a raw AxiosError (network / timeout / cancelled) into an HttpError.
 * If the AxiosError contains a response, delegates to `mapStatusToError`.
 */
export const convertAxiosError = (error: AxiosError): Error => {
  const requestMetadata = getRequestMetadata({
    url: error.config?.url,
    baseURL: error.config?.baseURL,
    method: error.config?.method,
  });

  if (error.code === AXIOS_ERROR_CODE.CANCELLED) {
    return new HttpCancelledError(requestMetadata.requestUrl, requestMetadata.method, error);
  }

  if (error.code === AXIOS_ERROR_CODE.TIMEOUT || error.code === AXIOS_ERROR_CODE.TIMEOUT_ALT) {
    const timeout = error.config?.timeout ?? 0;
    return new HttpTimeoutError(timeout, requestMetadata.requestUrl, requestMetadata.method, error);
  }

  if (error.code === AXIOS_ERROR_CODE.NETWORK || !error.response) {
    return new HttpNetworkError(
      error.message,
      requestMetadata.requestUrl,
      requestMetadata.method,
      error,
    );
  }

  const { status } = error.response;
  const message = extractErrorMessage(error.response) ?? error.message;
  return mapStatusToError(
    status,
    message,
    requestMetadata.requestUrl,
    requestMetadata.method,
    error,
  );
};

/**
 * Converts a non-2xx fulfilled response (status >= 400) into an HttpError.
 * Only called when `validateStatus: () => true` lets all statuses through.
 */
export const convertResponseError = (response: AxiosResponse): Error => {
  const requestMetadata = getRequestMetadata({
    url: response.config?.url,
    baseURL: response.config?.baseURL,
    method: response.config?.method,
  });
  const { status } = response;
  const message = extractErrorMessage(response) ?? `HTTP ${status}`;
  return mapStatusToError(status, message, requestMetadata.requestUrl, requestMetadata.method);
};

// =============================================================================
// Interceptor
// =============================================================================

/**
 * Creates the error normalizer response interceptor.
 *
 * - `onFulfilled`: throws when `response.status >= 400`
 * - `onRejected`: converts raw AxiosError into a typed HttpError
 */
export const createErrorNormalizerInterceptor = (options: ErrorNormalizerOptions = {}) => {
  const { debug = false } = options;
  const logger = createDebugLogger('HttpClient:ErrorNormalizerInterceptor', debug);

  const onFulfilled = (response: AxiosResponse): AxiosResponse => {
    if (response.status >= 400) {
      logger.debug('Response error', { status: response.status, url: response.config?.url });
      throw convertResponseError(response);
    }
    return response;
  };

  const onRejected = (error: unknown): never => {
    if (isAxiosError(error)) {
      logger.debug('Axios error', {
        code: error.code,
        message: error.message,
        status: error.response?.status,
      });
      throw convertAxiosError(error);
    }

    throw error;
  };

  return { onFulfilled, onRejected };
};

/**
 * Registers the error normalizer interceptor on the given axios instance.
 *
 * @returns Interceptor ID for removal via `instance.interceptors.response.eject`.
 */
export const setupErrorNormalizerInterceptor = (
  instance: AxiosInstance,
  options: ErrorNormalizerOptions = {},
): number => {
  const { onFulfilled, onRejected } = createErrorNormalizerInterceptor(options);
  return instance.interceptors.response.use(onFulfilled, onRejected);
};
