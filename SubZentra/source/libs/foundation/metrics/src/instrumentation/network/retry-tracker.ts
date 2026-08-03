/**
 * Retry Tracker
 * @module instrumentation/network/retry-tracker
 */

import axios, {
  type AxiosInstance,
  type AxiosResponseHeaders,
  type RawAxiosResponseHeaders,
} from 'axios';

import {
  extractRoute,
  normalizeError,
  sanitizeUrl,
  sleep,
} from '@open-zentra/foundation-utils';

import { getSpanAttributes } from '../../core/context-manager';
import { getMeter } from '../../core/otel-provider';
import type { NetworkSignalConfig } from '../../types';

/**
 * Retry state for a request
 */
interface RetryState {
  url: string;
  method: string;
  attempts: number;
  firstAttemptTime: number;
  lastAttemptTime: number;
  errors: string[];
}

/**
 * Retry tracker state
 */
interface RetryTrackerState {
  config: NetworkSignalConfig;
  requests: Map<string, RetryState>;
  maxRetries: number;
}

let state: RetryTrackerState | null = null;

/**
 * Initialize retry tracker
 */
export const initializeRetryTracker = (config: NetworkSignalConfig): void => {
  state = {
    config,
    requests: new Map(),
    maxRetries: 10, // Maximum retries to track before cleanup
  };
};

/**
 * Generate a key for a request
 */
const getRequestKey = (url: string, method: string): string => `${method}:${sanitizeUrl(url)}`;

/**
 * Record retry metric
 */
const recordRetryMetric = (retryState: RetryState): void => {
  try {
    const meter = getMeter();
    const spanAttributes = getSpanAttributes();
    const route = extractRoute(retryState.url);

    // Retry counter
    const retryCounter = meter.createCounter('http_client_retries_total', {
      description: 'Total number of HTTP client request retries',
    });

    retryCounter.add(1, {
      ...spanAttributes,
      'http.method': retryState.method,
      'http.route': route,
      'retry.attempt': retryState.attempts,
    });

    // Retry histogram (time between attempts)
    if (retryState.attempts > 1) {
      const retryDelayHistogram = meter.createHistogram('http_client_retry_delay_ms', {
        description: 'Time between retry attempts in milliseconds',
        unit: 'ms',
      });

      const delay = retryState.lastAttemptTime - retryState.firstAttemptTime;
      retryDelayHistogram.record(delay / (retryState.attempts - 1), {
        ...spanAttributes,
        'http.method': retryState.method,
        'http.route': route,
      });
    }
  } catch (e) {
    console.error('[FoundationMetrics] Error recording retry metric:', e);
  }
};

/**
 * Track a retry attempt
 */
export const trackRetryAttempt = (url: string, method: string, errorMessage?: string): number => {
  if (!state?.config.trackRetries) {
    return 0;
  }

  const key = getRequestKey(url, method);
  const now = performance.now();

  let retryState = state.requests.get(key);

  if (!retryState) {
    retryState = {
      url: sanitizeUrl(url),
      method,
      attempts: 1,
      firstAttemptTime: now,
      lastAttemptTime: now,
      errors: errorMessage ? [errorMessage] : [],
    };
    state.requests.set(key, retryState);
    return 0; // First attempt, not a retry
  }

  // Check if this is a new request sequence (more than 30 seconds since last attempt)
  if (now - retryState.lastAttemptTime > 30000) {
    // Reset retry state
    retryState.attempts = 1;
    retryState.firstAttemptTime = now;
    retryState.lastAttemptTime = now;
    retryState.errors = errorMessage ? [errorMessage] : [];
    return 0;
  }

  // Increment retry count
  retryState.attempts++;
  retryState.lastAttemptTime = now;
  if (errorMessage) {
    retryState.errors.push(errorMessage);
  }

  const retryCount = retryState.attempts - 1;

  // Record retry metric
  recordRetryMetric(retryState);

  // Cleanup if too many retries
  if (retryState.attempts > state.maxRetries) {
    state.requests.delete(key);
  }

  return retryCount;
};

/**
 * Mark a request as successful (clear retry state)
 */
export const markRequestSuccess = (url: string, method: string): void => {
  if (!state) {
    return;
  }

  const key = getRequestKey(url, method);
  state.requests.delete(key);
};

/**
 * Get current retry count for a request
 */
export const getRetryCount = (url: string, method: string): number => {
  if (!state) {
    return 0;
  }

  const key = getRequestKey(url, method);
  const retryState = state.requests.get(key);

  return retryState ? retryState.attempts - 1 : 0;
};

/**
 * Get all tracked retry states (for debugging)
 */
export const getRetryStates = (): Map<string, RetryState> => state?.requests ?? new Map();

/**
 * Clear all retry states
 */
export const clearRetryStates = (): void => {
  state?.requests.clear();
};

/**
 * Cleanup stale retry states (older than 5 minutes)
 */
export const cleanupStaleRetryStates = (): void => {
  if (!state) {
    return;
  }

  const now = performance.now();
  const staleThreshold = 5 * 60 * 1000; // 5 minutes

  for (const [key, retryState] of state.requests.entries()) {
    if (now - retryState.lastAttemptTime > staleThreshold) {
      state.requests.delete(key);
    }
  }
};

/**
 * Create a fetch wrapper with retry support
 */
export const createRetryFetch = (
  maxRetries = 3,
  retryDelay = 1000,
  retryOn: number[] = [500, 502, 503, 504],
  axiosInstance?: AxiosInstance,
): typeof fetch => {
  const resolvedAxiosInstance = axiosInstance ?? state?.config.axiosInstance ?? axios;

  const toHeadersRecord = (headers: Headers): Record<string, string> => {
    const result: Record<string, string> = {};
    headers.forEach((value, key) => {
      result[key] = value;
    });
    return result;
  };

  const toResponseHeaders = (headers: RawAxiosResponseHeaders | AxiosResponseHeaders): Headers => {
    const responseHeaders = new Headers();
    Object.entries(headers).forEach(([key, value]) => {
      if (typeof value === 'string') {
        responseHeaders.set(key, value);
      } else if (Array.isArray(value)) {
        responseHeaders.set(key, value.join(', '));
      }
    });
    return responseHeaders;
  };

  const buildResponseFromAxios = (
    status: number,
    statusText: string,
    headers: RawAxiosResponseHeaders | AxiosResponseHeaders,
    data: unknown,
  ): Response => {
    const normalizedBody =
      data instanceof ArrayBuffer || typeof data === 'string' || data instanceof Blob
        ? data
        : JSON.stringify(data ?? {});

    return new Response(normalizedBody, {
      status,
      statusText,
      headers: toResponseHeaders(headers),
    });
  };

  const retryFetch = async (input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
    const request = new Request(input, init);
    const url = request.url;
    const method = request.method || 'GET';
    const requestHeaders = toHeadersRecord(request.headers);
    const requestBody =
      request.method === 'GET' || request.method === 'HEAD'
        ? undefined
        : await request.clone().arrayBuffer();

    let lastError: Error | null = null;

    for (let attempt = 0; attempt <= maxRetries; attempt++) {
      try {
        if (attempt > 0) {
          trackRetryAttempt(url, method, lastError?.message);
          await sleep(retryDelay * Math.pow(2, attempt - 1)); // Exponential backoff
        }

        const axiosResponse = await resolvedAxiosInstance.request<ArrayBuffer>({
          url,
          method,
          headers: requestHeaders,
          data: requestBody,
          responseType: 'arraybuffer',
          withCredentials: request.credentials === 'include',
          validateStatus: () => true,
        });
        const response = buildResponseFromAxios(
          axiosResponse.status,
          axiosResponse.statusText,
          axiosResponse.headers,
          axiosResponse.data,
        );

        if (retryOn.includes(response.status) && attempt < maxRetries) {
          lastError = new Error(`HTTP ${response.status}`);
          continue;
        }

        if (attempt > 0) {
          markRequestSuccess(url, method);
        }

        return response;
      } catch (error) {
        lastError = normalizeError(error);

        if (attempt === maxRetries) {
          throw error;
        }
      }
    }

    throw lastError;
  };

  return retryFetch;
};
