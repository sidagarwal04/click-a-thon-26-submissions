/**
 * HTTP Context
 *
 * Public React context exposing the configured axios instance.
 *
 * @module provider/http-context
 */

import { createContext, useContext } from 'react';

import type { HttpContextValue } from '../core/types';

// =============================================================================
// Default Value
// =============================================================================

/**
 * Default context value used before the provider has initialised.
 * `axios` is null — consumers must check `isInitialized` before using it.
 */
const DEFAULT_HTTP_CONTEXT_VALUE: HttpContextValue = {
  axios: null,
  isInitialized: false,
  baseUrl: '',
};

// =============================================================================
// Context
// =============================================================================

export const HttpContext = createContext<HttpContextValue>(DEFAULT_HTTP_CONTEXT_VALUE);

HttpContext.displayName = 'HttpContext';

// =============================================================================
// Hook
// =============================================================================

/**
 * Low-level context accessor.
 *
 * Prefer `useHttp` (from hooks/use-http) in application code.
 * This hook is exposed for the provider and for `useHttp` itself.
 */
export const useHttpContext = (): HttpContextValue => useContext(HttpContext);
