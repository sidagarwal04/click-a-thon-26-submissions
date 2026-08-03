/**
 * Retry Response Interceptor
 *
 * Implements automatic retry with exponential backoff for transient failures.
 *
 * IMPORTANT: This interceptor runs BEFORE the error-normalizer in the response
 * chain. Because the axios instance is configured with `validateStatus: () => true`,
 * non-2xx responses arrive as fulfilled (not rejected). Therefore:
 *
 * - `onFulfilled` checks response.status against the configured retryable status
 *   codes (e.g. 408, 429, 500–504).
 * - `onRejected` handles raw AxiosError instances (timeout, network errors,
 *   cancelled) — NOT HttpError instances (those don't exist yet).
 *
 * @module interceptors/response/retry-interceptor
 */

import type { AxiosError, AxiosInstance, AxiosResponse, InternalAxiosRequestConfig } from 'axios';
import { isAxiosError } from 'axios';

import { createDebugLogger, sleep } from '@open-zentra/foundation-utils';

import { AXIOS_ERROR_CODE } from '../../core/constants';
import { getRequestMetadata } from '../../core/request-metadata';
import { calculateRetryDelayMs, isRetryableStatusCode } from '../../core/retry-utils';
import type { HttpRetryConfig } from '../../core/types';

// =============================================================================
// Types
// =============================================================================

export interface RetryInterceptorOptions {
  readonly retry: HttpRetryConfig;
  readonly debug?: boolean;
}

// =============================================================================
// Helpers
// =============================================================================

/**
 * Determines whether a fulfilled response status is retryable based on the
 * configured retryable status code list.
 */
const isRetryableAxiosError = (
  error: unknown,
  retryOnNetworkError: boolean,
): error is AxiosError => {
  if (!isAxiosError(error)) return false;

  if (error.code === AXIOS_ERROR_CODE.CANCELLED) return false;

  if (
    retryOnNetworkError &&
    (error.code === AXIOS_ERROR_CODE.NETWORK ||
      error.code === AXIOS_ERROR_CODE.TIMEOUT ||
      error.code === AXIOS_ERROR_CODE.TIMEOUT_ALT)
  ) {
    return true;
  }

  return false;
};

/**
 * Performs the retry cycle: waits for backoff, bumps metadata, re-dispatches.
 */
const executeRetry = async (
  instance: AxiosInstance,
  config: InternalAxiosRequestConfig,
  retry: HttpRetryConfig,
  logger: ReturnType<typeof createDebugLogger>,
): Promise<AxiosResponse> => {
  const retryCount = config.__oiHttpRetryCount ?? 0;
  const metadata = getRequestMetadata(config);

  if (retryCount >= retry.maxRetries) {
    logger.debug(
      `Max retries (${retry.maxRetries}) exceeded for`,
      metadata.requestUrl ?? config.url,
    );
    return Promise.reject(new Error(`Max retries (${retry.maxRetries}) exceeded`));
  }

  const delay = calculateRetryDelayMs(retryCount, retry, true);
  logger.debug(
    `Retrying request (attempt ${retryCount + 1}/${retry.maxRetries}) after ${Math.round(delay)}ms`,
    {
      url: metadata.requestUrl ?? config.url,
      method: metadata.method,
    },
  );

  await sleep(delay);

  config.__oiHttpRetryCount = retryCount + 1;
  if (!config.__oiHttpRetryStartTime) {
    config.__oiHttpRetryStartTime = Date.now();
  }

  return instance.request(config);
};

// =============================================================================
// Interceptor
// =============================================================================

/**
 * Creates the retry response interceptor.
 *
 * - `onFulfilled`: retries when `response.status` is in the configured
 *   retryable status codes list.
 * - `onRejected`: retries on raw AxiosError timeout / network errors.
 */
export const createRetryInterceptor = (
  instance: AxiosInstance,
  options: RetryInterceptorOptions,
) => {
  const { retry, debug = false } = options;
  const logger = createDebugLogger('HttpClient:RetryInterceptor', debug);

  const onFulfilled = (response: AxiosResponse): AxiosResponse | Promise<AxiosResponse> => {
    if (!retry.enabled) return response;

    if (isRetryableStatusCode(response.status, retry.retryableStatusCodes)) {
      const config = response.config;
      const retryCount = config.__oiHttpRetryCount ?? 0;

      if (retryCount >= retry.maxRetries) {
        return response;
      }

      return executeRetry(instance, config, retry, logger);
    }

    return response;
  };

  const onRejected = async (error: unknown): Promise<AxiosResponse> => {
    if (!retry.enabled) throw error;

    if (!isRetryableAxiosError(error, retry.retryOnNetworkError)) {
      throw error;
    }

    const config = error.config;
    if (!config) throw error;

    const retryCount = config.__oiHttpRetryCount ?? 0;
    if (retryCount >= retry.maxRetries) {
      logger.debug(`Max retries (${retry.maxRetries}) exceeded for`, config.url);
      throw error;
    }

    return executeRetry(instance, config, retry, logger);
  };

  return { onFulfilled, onRejected };
};

/**
 * Registers the retry interceptor on the given axios instance.
 *
 * @returns Interceptor ID for removal via `instance.interceptors.response.eject`.
 */
export const setupRetryInterceptor = (
  instance: AxiosInstance,
  options: RetryInterceptorOptions,
): number => {
  const { onFulfilled, onRejected } = createRetryInterceptor(instance, options);
  return instance.interceptors.response.use(onFulfilled, onRejected);
};

/**
 * Reads the retry attempt count from a request config.
 */
export const getRetryCount = (config: InternalAxiosRequestConfig): number =>
  config.__oiHttpRetryCount ?? 0;

/**
 * Reads the total retry duration (ms) from a request config.
 * Returns 0 when no retries have been attempted.
 */
export const getRetryDuration = (config: InternalAxiosRequestConfig): number => {
  const startTime = config.__oiHttpRetryStartTime;
  return startTime ? Date.now() - startTime : 0;
};
