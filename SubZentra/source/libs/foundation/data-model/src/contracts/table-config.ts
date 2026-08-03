/**
 * Shared table configuration contracts.
 *
 * @module contracts/table-config
 */

import type { ZodType } from 'zod';

import type { ConflictStrategy } from '../types';
import type { RealtimeApplyStrategy, RealtimeDataKind } from '../types/realtime';
import type { DataFreshnessLevel } from './analytics';

/**
 * HTTP query descriptor for a table operation.
 */
export interface ApiQueryDescriptor<TArgs = unknown, TData = unknown> {
  readonly path: string | ((args: TArgs) => string);
  readonly method?: 'GET';
  readonly params?: (args: TArgs) => Record<string, unknown>;
  readonly mapResponse?: (response: unknown) => TData;
}

/**
 * HTTP mutation descriptor for a table operation.
 */
export interface ApiMutationDescriptor<TArgs = unknown, TData = unknown> {
  readonly method: 'POST' | 'PUT' | 'PATCH' | 'DELETE';
  readonly path: string | ((args: TArgs) => string);
  readonly params?: (args: TArgs) => Record<string, unknown>;
  readonly body?: (args: TArgs) => unknown;
  readonly mapResponse?: (response: unknown) => TData;
}

/**
 * API operation descriptors for a table.
 */
export interface UnifiedTableApiConfig<TQueryRef = unknown, TMutationRef = unknown> {
  readonly list?: TQueryRef;
  readonly get?: TQueryRef;
  readonly create?: TMutationRef;
  readonly update?: TMutationRef;
  readonly delete?: TMutationRef;
}

/**
 * Real-time configuration for a table.
 */
export interface UnifiedTableRealtimeConfig<TEntity = unknown, TSnapshot = unknown> {
  readonly topic: string;
  readonly events?: ReadonlyArray<RealtimeDataKind>;
  readonly entitySchema: ZodType<TEntity>;
  readonly snapshotSchema: ZodType<TSnapshot>;
  readonly versionField?: string;
  readonly getVersion?: (entity: TEntity) => number | null | undefined;
  readonly applyStrategy?: RealtimeApplyStrategy;
}

/**
 * Conflict merge rules for field-level resolution.
 */
export interface UnifiedTableMergeConfig {
  readonly serverFields?: ReadonlyArray<string>;
  readonly clientFields?: ReadonlyArray<string>;
  readonly deepMergeFields?: ReadonlyArray<string>;
  readonly customMerge?: (serverValue: unknown, clientValue: unknown, field: string) => unknown;
}

/**
 * Analytics configuration for a table.
 */
export interface TableAnalyticsConfig {
  readonly enabled: boolean;
  readonly freshness?: DataFreshnessLevel;
  readonly staleTime?: number;
}

/**
 * Canonical table configuration shared across foundation layers.
 */
export interface UnifiedTableConfig<
  TQueryRef = ApiQueryDescriptor,
  TMutationRef = ApiMutationDescriptor,
> {
  readonly name: string;
  readonly api?: UnifiedTableApiConfig<TQueryRef, TMutationRef>;
  readonly realtime?: UnifiedTableRealtimeConfig;
  readonly staleTime?: number;
  readonly gcTime?: number;
  readonly conflictStrategy?: ConflictStrategy;
  readonly mergeConfig?: UnifiedTableMergeConfig;
  readonly analytics?: TableAnalyticsConfig;
}
