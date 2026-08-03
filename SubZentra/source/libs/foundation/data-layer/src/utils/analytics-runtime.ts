import type { DuckDBRouter } from '@open-zentra/foundation-bridge';

export interface AnalyticsRuntimeResolverOptions {
  readonly duckdbRouter: DuckDBRouter | null;
  readonly initializeAnalytics: () => Promise<{
    readonly duckdbRouter: DuckDBRouter;
    readonly opfsManager: unknown | null;
  } | null>;
}

export const getAnalyticsRouterOrThrow = async (
  options: AnalyticsRuntimeResolverOptions,
): Promise<DuckDBRouter> => {
  const { duckdbRouter, initializeAnalytics } = options;

  if (duckdbRouter) {
    return duckdbRouter;
  }

  const analyticsRuntime = await initializeAnalytics();
  const runtimeRouter = analyticsRuntime?.duckdbRouter ?? null;
  if (!runtimeRouter) {
    throw new Error('DuckDB is not available in this environment');
  }

  return runtimeRouter;
};
