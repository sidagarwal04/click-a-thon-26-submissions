/**
 * useHttpInternals Hook
 *
 * Internal hook for sibling foundation libraries that need the axios
 * instance, config, or access-token retrieval function.
 *
 * NOT for application code — use `useHttp` instead.
 *
 * @module hooks/use-http-internals
 * @internal
 */

import type { HttpInternals } from '../core/types';
import { useHttpInternalsContext } from '../provider/http-internals-context';

/**
 * Returns the full HTTP internals value (axios, config, getAccessToken).
 *
 * @internal
 */
export const useHttpInternals = (): HttpInternals => useHttpInternalsContext();

/**
 * Convenience accessor for the getAccessToken function.
 *
 * @internal
 */
export const useGetAccessToken = (): (() => Promise<string | null>) => {
  const { getAccessToken } = useHttpInternalsContext();
  return getAccessToken;
};
