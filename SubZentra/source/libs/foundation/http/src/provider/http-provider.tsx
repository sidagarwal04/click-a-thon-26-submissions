/**
 * HTTP Provider
 *
 * React provider that creates and manages a configured axios instance,
 * exposing it via two contexts: a public one for application code and
 * an internal one for sibling foundation libraries.
 *
 * @module provider/http-provider
 */

import React, { useEffect, useMemo, useRef, useState } from 'react';


import { createDebugLogger } from '@open-zentra/foundation-utils';

import { createConfigSignature } from '../core/config-signature';
import type {
  HttpContextValue,
  HttpInternals,
  HttpProviderProps,
} from '../core/types';
import { createAxiosInstance } from '../instance/axios-factory';
import { removeInterceptors, setupInterceptors, type InterceptorIds } from '../interceptors/setup';
import { HttpContext } from './http-context';
import { HttpInternalsContext } from './http-internals-context';

// =============================================================================
// Provider Component
// =============================================================================

export const HttpProvider = ({
  config,
  children,
  authInternals,
}: HttpProviderProps): React.ReactElement => {
  // Interceptors are a side effect on the instance, so they stay in an effect —
  // and until they are attached, requests would miss auth. That is what this
  // flag is for, and setting it after the work is done is the point of it.
  const [isInitialized, setIsInitialized] = useState(false);

  const interceptorIdsRef = useRef<InterceptorIds | null>(null);
  const logger = useMemo(
    () => createDebugLogger('HttpProvider', config.debug ?? false),
    [config.debug],
  );

  const configSignature = useMemo(
    () =>
      createConfigSignature({
        config,
        authInternalsGetAccessToken: authInternals?.getAccessToken,
        authInternalsTransport: authInternals?.transport,
      }),
    [config, authInternals?.getAccessToken, authInternals?.transport],
  );

  // Derived, not stored. Building the client in an effect and pushing it into
  // state cost a render where consumers saw `axios: null` for no reason, and
  // three synchronous setStates in one effect is the cascading-render pattern
  // React Compiler flags. The client depends only on the config, so a memo says
  // that directly.
  const { instance: axiosInstance, resolvedConfig } = useMemo(
    () => createAxiosInstance(config),
    // configSignature hashes the config's contents, so this rebuilds when the
    // config meaningfully changes rather than on every new object identity.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [configSignature],
  );


  useEffect(() => {
    const instance = axiosInstance;
    const resolved = resolvedConfig;

    const getAccessToken =
      authInternals?.getAccessToken ??
      resolved.auth.getAccessToken ??
      (async () => null);
    const authTransport = authInternals?.transport ?? resolved.auth.transport;

    const ids = setupInterceptors(instance, resolved, {
      getAccessToken,
      authTransport,
      clientHeaders: config.clientHeaders,
    });

    interceptorIdsRef.current = ids;
    // The rule is right in general and wrong here. Child effects run before
    // parent effects, so a consumer can fire a request before these
    // interceptors exist — which is the entire reason this flag is published.
    // Signalling that an effect has completed is what a state flag is for, and
    // every alternative changes the provider's public contract.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setIsInitialized(true);

    logger.debug('Initialized with config:', {
      baseUrl: resolved.baseUrl,
      timeout: resolved.timeout,
      authEnabled: resolved.auth.enabled,
      retryEnabled: resolved.retry.enabled,
      circuitBreakerEnabled: resolved.circuitBreaker.enabled,
    });

    return () => {
      if (interceptorIdsRef.current) {
        removeInterceptors(instance, interceptorIdsRef.current);
        interceptorIdsRef.current = null;
      }

      logger.debug('Disposed');
    };
    // Re-wires when the config values or functions change.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [configSignature, logger, axiosInstance, resolvedConfig]);

  const getAccessToken = useMemo(
    () =>
      authInternals?.getAccessToken ??
      resolvedConfig.auth.getAccessToken ??
      (async () => null),
    [authInternals?.getAccessToken, resolvedConfig],
  );

  const authTransport = useMemo(
    () => authInternals?.transport ?? resolvedConfig.auth.transport,
    [authInternals?.transport, resolvedConfig],
  );

  const contextValue = useMemo<HttpContextValue>(
    () => ({
      axios: axiosInstance,
      isInitialized,
      baseUrl: resolvedConfig.baseUrl,
    }),
    [axiosInstance, resolvedConfig, isInitialized],
  );

  const internalsValue = useMemo<HttpInternals>(
    () => ({
      axios: axiosInstance,
      config,
      getAccessToken,
      authTransport,
    }),
    [authTransport, axiosInstance, config, getAccessToken],
  );

  return (
    <HttpContext.Provider value={contextValue}>
      <HttpInternalsContext.Provider value={internalsValue}>
        {children}
      </HttpInternalsContext.Provider>
    </HttpContext.Provider>
  );
};
