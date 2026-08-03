/**
 * Auth Request Interceptor
 *
 * Injects authentication token into request headers.
 *
 * @module interceptors/request/auth-interceptor
 */

import type { AxiosInstance, InternalAxiosRequestConfig } from 'axios';

import { createDebugLogger } from '@open-zentra/foundation-utils';

import { HTTP_HEADERS } from '../../core/constants';
import type { AuthConfig } from '../../core/types';

// =============================================================================
// Types
// =============================================================================

export interface AuthInterceptorOptions {
  readonly auth: AuthConfig;
  readonly getAccessToken: AuthConfig['getAccessToken'];
  readonly debug?: boolean;
}

// =============================================================================
// Interceptor
// =============================================================================

/**
 * Creates the auth request interceptor function.
 *
 * Injects Bearer token into the Authorization header when auth is enabled
 * and a token is available. Skips silently if the header is already set
 * or if token retrieval fails (the request proceeds unauthenticated).
 */
export const createAuthInterceptor = (options: AuthInterceptorOptions) => {
  const { auth, getAccessToken, debug } = options;
  const logger = createDebugLogger('HttpClient:AuthInterceptor', debug ?? false);

  return async (config: InternalAxiosRequestConfig): Promise<InternalAxiosRequestConfig> => {
    if (!auth.enabled) {
      return config;
    }

    if (config.headers?.[HTTP_HEADERS.AUTHORIZATION]) {
      return config;
    }

    try {
      const request = {
        audience: auth.audience ?? 'first_party_http',
        url: config.url,
        method: config.method,
      };

      if (auth.transport) {
        const transport = await auth.transport.getTransport(request);

        if (transport.kind === 'anonymous') {
          logger.debug('Anonymous auth transport resolved');
          return config;
        }

        if (transport.kind === 'cookie') {
          config.withCredentials = transport.withCredentials ?? true;
          logger.debug('Cookie auth transport resolved');
          return config;
        }

        config.withCredentials = transport.withCredentials ?? config.withCredentials;
        config.headers = config.headers ?? {};
        config.headers[HTTP_HEADERS.AUTHORIZATION] =
          `${transport.scheme ?? auth.tokenType ?? 'Bearer'} ${transport.token}`;
        logger.debug('Bearer auth transport resolved');
        return config;
      }

      const token = await getAccessToken?.(request);

      if (token) {
        const tokenType = auth.tokenType ?? 'Bearer';
        config.headers = config.headers ?? {};
        config.headers[HTTP_HEADERS.AUTHORIZATION] = `${tokenType} ${token}`;

        logger.debug('Auth token injected');
      } else {
        logger.debug('No auth token available');
      }
    } catch (error) {
      logger.warn('Failed to get auth token', error);
    }

    return config;
  };
};

/**
 * Registers the auth interceptor on the given axios instance.
 *
 * @returns Interceptor ID for removal via `instance.interceptors.request.eject`.
 */
export const setupAuthInterceptor = (
  instance: AxiosInstance,
  options: AuthInterceptorOptions,
): number => instance.interceptors.request.use(createAuthInterceptor(options), undefined);
