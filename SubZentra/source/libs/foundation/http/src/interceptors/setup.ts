/**
 * Interceptor Setup
 *
 * Orchestrates the registration of all interceptors on an axios instance.
 *
 * @module interceptors/setup
 */

import type { AxiosInstance } from 'axios';

import type { AuthConfig, ClientHeadersConfig, ResolvedHttpConfig } from '../core/types';
import { setupAuthInterceptor } from './request/auth-interceptor';
import { setupHeadersInterceptor } from './request/headers-interceptor';
import { setupParamsInterceptor } from './request/params-interceptor';
import { setupCircuitBreakerInterceptor } from './response/circuit-breaker-interceptor';
import { setupErrorNormalizerInterceptor } from './response/error-normalizer';
import { setupRetryInterceptor } from './response/retry-interceptor';
import { setupUnauthorizedHandlerInterceptor } from './response/unauthorized-handler';

// =============================================================================
// Types
// =============================================================================

/** Interceptor IDs for later removal via `eject`. */
export interface InterceptorIds {
  readonly request: {
    readonly headers: number;
    readonly params: number;
    readonly auth: number;
    readonly circuitBreaker?: number;
  };
  readonly response: {
    readonly circuitBreaker?: number;
    readonly errorNormalizer: number;
    readonly unauthorizedHandler: number;
    readonly retry: number;
  };
}

export interface SetupInterceptorsOptions {
  readonly getAccessToken: AuthConfig['getAccessToken'];
  readonly authTransport?: AuthConfig['transport'];
  readonly clientHeaders?: ClientHeadersConfig;
}

// =============================================================================
// Setup
// =============================================================================

/**
 * Registers all interceptors on the given axios instance.
 *
 * **Execution order matters.**
 *
 * Request interceptors (LIFO — last registered runs first):
 *  1. Auth      (runs last in registration → runs first at request time)
 *  2. Params
 *  3. Headers
 *
 * Response interceptors (FIFO — first registered runs first):
 *  1. Circuit breaker      → tracks host failures / short-circuits unhealthy hosts
 *  2. Retry                → retries before errors are normalised
 *  3. Unauthorized handler → triggers auth callback before normalisation
 *  4. Error normalizer     → converts raw responses/AxiosErrors to HttpErrors
 */
export const setupInterceptors = (
  instance: AxiosInstance,
  config: ResolvedHttpConfig,
  options: SetupInterceptorsOptions,
): InterceptorIds => {
  const { getAccessToken, authTransport, clientHeaders } = options;
  const { auth, retry, debug } = config;
  const resolvedAuth: AuthConfig = {
    ...auth,
    getAccessToken,
    transport: authTransport ?? auth.transport,
  };

  // -- Request interceptors (LIFO) -------------------------------------------

  const headersId = setupHeadersInterceptor(instance, {
    clientHeaders,
    debug,
  });

  const paramsId = setupParamsInterceptor(instance, {
    removeNullish: true,
    debug,
  });

  const authId = setupAuthInterceptor(instance, {
    auth: resolvedAuth,
    getAccessToken,
    debug,
  });

  // -- Response interceptors (FIFO) ------------------------------------------
  let circuitBreakerRequestId: number | undefined;
  let circuitBreakerResponseId: number | undefined;
  if (config.circuitBreaker.enabled) {
    const circuitBreakerSetup = setupCircuitBreakerInterceptor(instance, config.circuitBreaker);
    circuitBreakerRequestId = circuitBreakerSetup.requestInterceptorId;
    circuitBreakerResponseId = circuitBreakerSetup.responseInterceptorId;
  }

  const retryId = setupRetryInterceptor(instance, {
    retry,
    debug,
  });

  const unauthorizedHandlerId = setupUnauthorizedHandlerInterceptor(instance, {
    auth: resolvedAuth,
    debug,
  });

  const errorNormalizerId = setupErrorNormalizerInterceptor(instance, {
    debug,
  });

  return {
    request: {
      headers: headersId,
      params: paramsId,
      auth: authId,
      circuitBreaker: circuitBreakerRequestId,
    },
    response: {
      circuitBreaker: circuitBreakerResponseId,
      errorNormalizer: errorNormalizerId,
      unauthorizedHandler: unauthorizedHandlerId,
      retry: retryId,
    },
  };
};

/**
 * Removes all interceptors previously registered by `setupInterceptors`.
 */
export const removeInterceptors = (instance: AxiosInstance, ids: InterceptorIds): void => {
  instance.interceptors.request.eject(ids.request.headers);
  instance.interceptors.request.eject(ids.request.params);
  instance.interceptors.request.eject(ids.request.auth);
  if (ids.request.circuitBreaker !== undefined) {
    instance.interceptors.request.eject(ids.request.circuitBreaker);
  }

  if (ids.response.circuitBreaker !== undefined) {
    instance.interceptors.response.eject(ids.response.circuitBreaker);
  }
  instance.interceptors.response.eject(ids.response.errorNormalizer);
  instance.interceptors.response.eject(ids.response.unauthorizedHandler);
  instance.interceptors.response.eject(ids.response.retry);
};
