/**
 * Unauthorized Handler Response Interceptor
 *
 * Calls an optional callback when a 401/403 response is detected,
 * enabling the application to trigger token refresh or redirect to login.
 *
 * @module interceptors/response/unauthorized-handler
 */

import type { AxiosInstance, AxiosResponse } from 'axios';

import { createDebugLogger } from '@open-zentra/foundation-utils';

import { HTTP_STATUS } from '../../core/constants';
import type { AuthConfig } from '../../core/types';
import { isHttpForbiddenError, isHttpUnauthorizedError } from '../../errors/type-guards';

// =============================================================================
// Types
// =============================================================================

export interface UnauthorizedHandlerOptions {
  readonly auth: AuthConfig;
  readonly debug?: boolean;
}

// =============================================================================
// Interceptor
// =============================================================================

/**
 * Creates the unauthorized handler response interceptor.
 *
 * - `onFulfilled`: detects 401/403 status on fulfilled responses
 *   (with `validateStatus: () => true`, non-2xx arrive as fulfilled).
 * - `onRejected`: detects HttpUnauthorizedError / HttpForbiddenError
 *   that may have been thrown by a prior interceptor.
 *
 * The `onUnauthorized` callback receives `(statusCode, url?)` — no mock
 * AxiosResponse objects are constructed.
 */
export const createUnauthorizedHandlerInterceptor = (options: UnauthorizedHandlerOptions) => {
  const { auth, debug } = options;
  const logger = createDebugLogger('HttpClient:UnauthorizedHandlerInterceptor', debug ?? false);

  const handleUnauthorized = (statusCode: number, url?: string): void => {
    const code = statusCode === HTTP_STATUS.FORBIDDEN ? 'forbidden' : 'unauthorized';

    void auth.transport?.invalidate({
      code,
      statusCode,
      url,
    });
    auth.onUnauthorized?.(statusCode, url);
  };

  const onFulfilled = (response: AxiosResponse): AxiosResponse => {
    if (
      auth.enabled &&
      (response.status === HTTP_STATUS.UNAUTHORIZED || response.status === HTTP_STATUS.FORBIDDEN)
    ) {
      logger.debug('Unauthorized response detected', {
        status: response.status,
        url: response.config?.url,
      });
      handleUnauthorized(response.status, response.config?.url);
    }
    return response;
  };

  const onRejected = (error: unknown): never => {
    if (auth.enabled) {
      if (isHttpUnauthorizedError(error)) {
        logger.debug('Unauthorized error detected');
        handleUnauthorized(error.statusCode ?? 401, error.url);
      } else if (isHttpForbiddenError(error)) {
        logger.debug('Forbidden error detected');
        handleUnauthorized(error.statusCode ?? 403, error.url);
      }
    }

    throw error;
  };

  return { onFulfilled, onRejected };
};

/**
 * Registers the unauthorized handler interceptor on the given axios instance.
 *
 * @returns Interceptor ID for removal via `instance.interceptors.response.eject`.
 */
export const setupUnauthorizedHandlerInterceptor = (
  instance: AxiosInstance,
  options: UnauthorizedHandlerOptions,
): number => {
  const { onFulfilled, onRejected } = createUnauthorizedHandlerInterceptor(options);
  return instance.interceptors.response.use(onFulfilled, onRejected);
};
