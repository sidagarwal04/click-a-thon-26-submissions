/**
 * Retry Utilities
 *
 * Shared helpers for HTTP retry classification and backoff calculation.
 *
 * @module core/retry-utils
 */

import { isRetriableHttpStatus } from '@open-zentra/foundation-utils';

/**
 * Check whether an HTTP status should be retried.
 */
export const isRetryableStatusCode = (
  status: number,
  retryableStatusCodes: readonly number[],
): boolean => {
  if (retryableStatusCodes.length === 0) {
    return isRetriableHttpStatus(status);
  }

  return retryableStatusCodes.includes(status);
};

export interface RetryDelayConfig {
  readonly initialDelayMs: number;
  readonly maxDelayMs: number;
  readonly backoffMultiplier: number;
}

/**
 * Calculate exponential backoff delay with optional jitter.
 */
export const calculateRetryDelayMs = (
  attempt: number,
  config: RetryDelayConfig,
  includeJitter = true,
): number => {
  const exponentialDelay = config.initialDelayMs * Math.pow(config.backoffMultiplier, attempt);
  const cappedDelay = Math.min(exponentialDelay, config.maxDelayMs);

  if (!includeJitter) {
    return cappedDelay;
  }

  return Math.floor(cappedDelay + cappedDelay * 0.5 * Math.random());
};
