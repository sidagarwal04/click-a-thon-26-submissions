/**
 * Utilities for normalizing config objects by removing explicit `undefined` values.
 *
 * @module core/config-normalization
 */

import type { DataLayerConfig } from './types';

type UnknownRecord = Record<string, unknown>;

/**
 * Build a shallow copy that excludes keys with `undefined` values.
 */
export const pickDefined = <T extends UnknownRecord>(input: T): Partial<T> => {
  const output: Partial<T> = {};

  for (const [rawKey, rawValue] of Object.entries(input)) {
    if (rawValue === undefined) {
      continue;
    }

    const key = rawKey as keyof T;
    output[key] = rawValue as T[keyof T];
  }

  return output;
};

/**
 * Create a stable, hashable fingerprint for datasource endpoint descriptors.
 */
export const getDatasourceEndpointFingerprint = (
  datasourceEndpoint: DataLayerConfig['datasourceEndpoint'],
): Record<string, unknown> | null => {
  if (!datasourceEndpoint || typeof datasourceEndpoint !== 'object') {
    return null;
  }

  const value = datasourceEndpoint as unknown as Record<string, unknown>;
  return {
    path: value['path'] ?? null,
    method: value['method'] ?? null,
  };
};

/**
 * Normalize provider config before constructing the container.
 */
export const createContainerConfig = (config: DataLayerConfig): DataLayerConfig => ({
  ...pickDefined({
    tables: config.tables,
    datasourceEndpoint: config.datasourceEndpoint,
    conflictStrategy: config.conflictStrategy,
    enableCrossTab: config.enableCrossTab,
    enableAnalytics: config.enableAnalytics,
    defaultStaleTime: config.defaultStaleTime,
    defaultGcTime: config.defaultGcTime,
    cache: config.cache,
    debug: config.debug,
    onSyncError: config.onSyncError,
  }),
  axiosInstance: config.axiosInstance,
  websocket: config.websocket,
});
