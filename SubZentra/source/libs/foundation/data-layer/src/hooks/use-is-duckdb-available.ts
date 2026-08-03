/**
 * useIsDuckDBAvailable Hook
 * Convenience hook to check DuckDB availability.
 *
 * @module hooks/use-is-duckdb-available
 */

import { useDataLayer } from '../provider/data-layer-context';

/**
 * Hook to check if DuckDB is available for analytics queries
 *
 * Uses DuckDBRouter from foundation-bridge.
 *
 * @returns `true` if DuckDB is available, `false` otherwise
 *
 * @example
 * ```tsx
 * const isDuckDBAvailable = useIsDuckDBAvailable();
 *
 * if (!isDuckDBAvailable) {
 *   return <div>Analytics not available</div>;
 * }
 *
 * return <AnalyticsDashboard />;
 * ```
 */
export const useIsDuckDBAvailable = (): boolean => {
  const { isDuckDBAvailable } = useDataLayer();
  return isDuckDBAvailable;
};
