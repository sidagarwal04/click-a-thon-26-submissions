/**
 * Headers Request Interceptor
 *
 * Adds client identification and tracking headers to requests.
 *
 * @module interceptors/request/headers-interceptor
 */

import type { AxiosInstance, InternalAxiosRequestConfig } from 'axios';

import { createDebugLogger, generateId } from '@open-zentra/foundation-utils';

import { CLIENT_HEADERS, HTTP_HEADERS } from '../../core/constants';
import type { ClientHeadersConfig } from '../../core/types';

// =============================================================================
// Types
// =============================================================================

export interface HeadersInterceptorOptions {
  readonly clientHeaders?: ClientHeadersConfig;
  readonly debug?: boolean;
}

// =============================================================================
// Interceptor
// =============================================================================

/**
 * Creates the headers request interceptor function.
 *
 * Adds:
 * - X-Request-ID for distributed request tracing
 * - X-Client-ID, X-Client-Version, X-Client-Platform, X-Client-Session-ID
 *   for client identification (when configured)
 */
export const createHeadersInterceptor = (options: HeadersInterceptorOptions) => {
  const { clientHeaders, debug } = options;
  const logger = createDebugLogger('HttpClient:HeadersInterceptor', debug ?? false);

  return (config: InternalAxiosRequestConfig): InternalAxiosRequestConfig => {
    config.headers = config.headers ?? {};

    if (!config.headers[HTTP_HEADERS.X_REQUEST_ID]) {
      config.headers[HTTP_HEADERS.X_REQUEST_ID] = generateId();
    }

    if (clientHeaders) {
      if (clientHeaders.clientId && !config.headers[CLIENT_HEADERS.X_CLIENT_ID]) {
        config.headers[CLIENT_HEADERS.X_CLIENT_ID] = clientHeaders.clientId;
      }

      if (clientHeaders.clientVersion && !config.headers[CLIENT_HEADERS.X_CLIENT_VERSION]) {
        config.headers[CLIENT_HEADERS.X_CLIENT_VERSION] = clientHeaders.clientVersion;
      }

      if (clientHeaders.platform && !config.headers[CLIENT_HEADERS.X_CLIENT_PLATFORM]) {
        config.headers[CLIENT_HEADERS.X_CLIENT_PLATFORM] = clientHeaders.platform;
      }

      if (clientHeaders.sessionId && !config.headers[CLIENT_HEADERS.X_CLIENT_SESSION_ID]) {
        const sessionId =
          typeof clientHeaders.sessionId === 'function'
            ? clientHeaders.sessionId()
            : clientHeaders.sessionId;
        config.headers[CLIENT_HEADERS.X_CLIENT_SESSION_ID] = sessionId;
      }
    }

    logger.debug('Request headers added', {
      requestId: config.headers[HTTP_HEADERS.X_REQUEST_ID],
      clientId: config.headers[CLIENT_HEADERS.X_CLIENT_ID],
    });

    return config;
  };
};

/**
 * Registers the headers interceptor on the given axios instance.
 *
 * @returns Interceptor ID for removal via `instance.interceptors.request.eject`.
 */
export const setupHeadersInterceptor = (
  instance: AxiosInstance,
  options: HeadersInterceptorOptions,
): number => instance.interceptors.request.use(createHeadersInterceptor(options), undefined);
