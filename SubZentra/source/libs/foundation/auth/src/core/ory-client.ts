/**
 * Ory Client Singleton
 *
 * Provides a singleton factory for Ory API clients (Kratos and Hydra).
 *
 * @module core/ory-client
 */

import { Configuration, FrontendApi, OAuth2Api } from '@ory/client-fetch';
import isEqual from 'react-fast-compare';

import {
  createDeepEqualComparison,
  createSingletonFactory,
} from '@open-zentra/foundation-utils';

import type { OryConfig } from './types';

// =============================================================================
// Types
// =============================================================================

/**
 * Ory client configuration
 */
export interface OryClientConfig {
  /** Ory Kratos public URL */
  kratosUrl: string;
  /** Ory Hydra public URL (optional) */
  hydraUrl?: string;
}

/**
 * Ory client instance containing API clients
 */
export interface OryClientInstance {
  /** Kratos Frontend API for browser-based auth flows */
  readonly frontend: FrontendApi;
  /** Hydra OAuth2 API for token operations (null if hydraUrl not provided) */
  readonly oauth2: OAuth2Api | null;
  /** Configuration used to create this instance */
  readonly config: OryClientConfig;
}

// =============================================================================
// Client Factory
// =============================================================================

/**
 * Create Ory client instance from configuration
 */
const createOryClientInstance = (config: OryClientConfig): OryClientInstance => {
  // Validate configuration
  if (!config.kratosUrl) {
    throw new Error('[OryClient] kratosUrl is required');
  }

  // Normalize URLs (remove trailing slashes)
  const kratosUrl = config.kratosUrl.replace(/\/+$/, '');
  const hydraUrl = config.hydraUrl?.replace(/\/+$/, '');

  // Create Kratos configuration
  const kratosConfig = new Configuration({
    basePath: kratosUrl,
    credentials: 'include', // Important: Always include cookies for session management
  });

  // Create Frontend API (Kratos)
  const frontend = new FrontendApi(kratosConfig);

  // Create OAuth2 API (Hydra) if configured
  let oauth2: OAuth2Api | null = null;
  if (hydraUrl) {
    const hydraConfig = new Configuration({
      basePath: hydraUrl,
      credentials: 'include',
    });
    oauth2 = new OAuth2Api(hydraConfig);
  }

  return {
    frontend,
    oauth2,
    config: { kratosUrl, hydraUrl },
  };
};

/**
 * Singleton factory for Ory client
 */
const oryClientFactory = createSingletonFactory(
  (config: OryClientConfig) => createOryClientInstance(config),
  {
    name: 'OryClient',
    warnOnConfigOverride: true,
    compareConfig: createDeepEqualComparison(isEqual, 'OryClient'),
  },
);

// =============================================================================
// Public API
// =============================================================================

/**
 * Get or create the Ory client instance
 *
 * @param config - Ory client configuration
 * @returns Ory client instance
 *
 * @example
 * ```typescript
 * const client = getOryClient({ kratosUrl: 'https://your-project.ory.cloud' });
 *
 * // Use the frontend API
 * const session = await client.frontend.toSession();
 *
 * // Use the OAuth2 API (if configured)
 * if (client.oauth2) {
 *   const token = await client.oauth2.oauth2TokenExchange({ ... });
 * }
 * ```
 */
export const getOryClient = (config: OryClientConfig): OryClientInstance =>
  oryClientFactory.getInstance(config);

/**
 * Reset the Ory client singleton (for testing)
 */
export const resetOryClient = async (): Promise<void> => oryClientFactory.reset();

/**
 * Check if an Ory client instance exists
 */
export const hasOryClient = (): boolean => oryClientFactory.hasInstance();

/**
 * Create Ory client config from AuthConfig
 *
 * @param config - Auth configuration
 * @returns Ory client configuration
 */
export const createOryClientConfig = (oryConfig: OryConfig): OryClientConfig => ({
  kratosUrl: oryConfig.kratosUrl,
  hydraUrl: oryConfig.hydraUrl,
});
