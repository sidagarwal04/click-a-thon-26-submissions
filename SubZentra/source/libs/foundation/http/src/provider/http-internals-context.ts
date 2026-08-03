/**
 * HTTP Internals Context
 *
 * Internal context for sibling foundation libraries that need access to the
 * configured axios instance and token retrieval. NOT for application code.
 *
 * @module provider/http-internals-context
 */

import { createContext, useContext } from 'react';

import type { HttpClientConfig, HttpInternals } from '../core/types';

// =============================================================================
// Default Value
// =============================================================================

const DEFAULT_CONFIG: HttpClientConfig = { baseUrl: '' };

/**
 * Default internals value used before the provider has initialised.
 * `axios` is null — consumers must guard against this.
 */
const DEFAULT_HTTP_INTERNALS: HttpInternals = {
  axios: null,
  config: DEFAULT_CONFIG,
  getAccessToken: async () => null,
};

// =============================================================================
// Context
// =============================================================================

export const HttpInternalsContext = createContext<HttpInternals>(DEFAULT_HTTP_INTERNALS);

HttpInternalsContext.displayName = 'HttpInternalsContext';

// =============================================================================
// Hook
// =============================================================================

/**
 * Low-level internals context accessor.
 *
 * Prefer `useHttpInternals` (from hooks/use-http-internals) in library code.
 *
 * @internal
 */
export const useHttpInternalsContext = (): HttpInternals => useContext(HttpInternalsContext);
