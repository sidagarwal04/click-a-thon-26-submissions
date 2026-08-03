/**
 * Axios Factory
 *
 * Factory functions for creating configured axios instances.
 * ResolvedHttpConfig lives in core/types.ts — this module only resolves and creates.
 *
 * @module instance/axios-factory
 */

import axios, { type AxiosInstance, type CreateAxiosDefaults } from 'axios';

import {
  CONTENT_TYPES,
  DEFAULT_AUTH_CONFIG,
  DEFAULT_HTTP_CIRCUIT_BREAKER_CONFIG,
  DEFAULT_HTTP_RETRY_CONFIG,
  DEFAULT_TIMEOUT_MS,
  HTTP_HEADERS,
} from '../core/constants';
import type { HttpClientConfig, ResolvedHttpConfig } from '../core/types';

// =============================================================================
// Configuration Resolution
// =============================================================================

/**
 * Resolves a partial HttpClientConfig into a fully-defaulted ResolvedHttpConfig.
 */
export const resolveHttpConfig = (config: HttpClientConfig): ResolvedHttpConfig => ({
  baseUrl: config.baseUrl,
  timeout: config.timeout ?? DEFAULT_TIMEOUT_MS,
  withCredentials: config.withCredentials ?? false,
  defaultHeaders: {
    [HTTP_HEADERS.CONTENT_TYPE]: CONTENT_TYPES.JSON,
    [HTTP_HEADERS.ACCEPT]: CONTENT_TYPES.JSON,
    ...config.defaultHeaders,
  },
  retry: {
    ...DEFAULT_HTTP_RETRY_CONFIG,
    ...config.retry,
  },
  auth: {
    ...DEFAULT_AUTH_CONFIG,
    ...config.auth,
  },
  circuitBreaker: {
    ...DEFAULT_HTTP_CIRCUIT_BREAKER_CONFIG,
    ...config.circuitBreaker,
  },
  debug: config.debug ?? false,
});

// =============================================================================
// Axios Instance Factory
// =============================================================================

/**
 * Creates a bare axios instance from the given configuration.
 *
 * No interceptors are attached — use `setupInterceptors` from
 * `interceptors/setup` to register them separately.
 */
export const createAxiosInstance = (
  config: HttpClientConfig,
): {
  instance: AxiosInstance;
  resolvedConfig: ResolvedHttpConfig;
} => {
  const resolvedConfig = resolveHttpConfig(config);

  const axiosConfig: CreateAxiosDefaults = {
    baseURL: resolvedConfig.baseUrl,
    timeout: resolvedConfig.timeout,
    withCredentials: resolvedConfig.withCredentials,
    headers: { ...resolvedConfig.defaultHeaders },
    validateStatus: () => true,
    paramsSerializer: {
      indexes: null,
    },
  };

  const instance = axios.create(axiosConfig);

  return { instance, resolvedConfig };
};

/**
 * Creates an axios instance bundled with the resolved getAccessToken function.
 *
 * This is a convenience wrapper over `createAxiosInstance` for callers that
 * need the token accessor alongside the instance (e.g. provider setup).
 */
export const createConfiguredAxiosInstance = (
  config: HttpClientConfig,
  options?: {
    readonly getAccessToken?: ResolvedHttpConfig['auth']['getAccessToken'];
  },
): {
  instance: AxiosInstance;
  resolvedConfig: ResolvedHttpConfig;
  getAccessToken: NonNullable<ResolvedHttpConfig['auth']['getAccessToken']>;
} => {
  const { instance, resolvedConfig } = createAxiosInstance(config);

  const getAccessToken =
    options?.getAccessToken ?? resolvedConfig.auth.getAccessToken ?? (async () => null);

  return { instance, resolvedConfig, getAccessToken };
};
