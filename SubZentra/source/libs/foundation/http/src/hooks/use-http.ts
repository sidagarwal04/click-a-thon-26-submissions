/**
 * useHttp Hook
 *
 * Main hook for accessing the configured HTTP client in application code.
 *
 * @module hooks/use-http
 */

import type { HttpContextValue } from '../core/types';
import { useHttpContext } from '../provider/http-context';

/**
 * Returns the configured axios instance and its initialisation status.
 *
 * Consumers should check `isInitialized` (or guard on `axios !== null`)
 * before making requests.
 *
 * @example
 * ```tsx
 * const { axios, isInitialized } = useHttp();
 *
 * if (!isInitialized) return <Spinner />;
 *
 * const response = await axios.get('/users');
 * ```
 */
export const useHttp = (): HttpContextValue => useHttpContext();
