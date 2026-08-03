/**
 * useDLMutateQueryEngine - Unified Mutation Hook
 *
 * Main mutation hook that routes to appropriate Data Layer mutation hooks
 * based on the operation type (create, update, delete).
 *
 * Features:
 * - Automatic operation detection from query
 * - Optimistic updates with provisional IDs
 * - Offline mutation queueing via data-layer
 * - Query invalidation
 *
 * NOTE: This hook delegates ALL execution to foundation-data-layer.
 * It does NOT directly access the HTTP transport directly.
 *
 * @module hooks/use-dl-mutate-query-engine
 */

import { useCallback, useMemo } from 'react';

import type { QueryKey } from '@tanstack/react-query';

import {
  useDataLayerInternals,
  useDLCreate,
  useDLDelete,
  useDLUpdate,
} from '@open-zentra/foundation-data-layer';
import { getEntityId as getDataModelEntityId } from '@open-zentra/foundation-data-model';
import { EMPTY_ARRAY } from '@open-zentra/foundation-utils';

import { getTableExtractor } from '../engine/table-extractor';
import {
  getAnyMutationReference,
  getAnyMutationReferenceFromRegistry,
  getMutationReference,
  resolveMutationOperation,
} from './internal/data-layer-adapters';
import {
  EXECUTION_PATHS,
  MUTATION_OPERATIONS,
  type MutationOperation,
  type UseDLMutateQueryEngineOptions,
  type UseDLMutateQueryEngineResult,
} from './types';

// =============================================================================
// HELPERS
// =============================================================================

/**
 * Default entity ID extractor
 */
const defaultGetEntityId = <TVariables>(variables: TVariables): string => {
  const entityId = getDataModelEntityId(variables);
  return entityId ?? '';
};

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === 'object' && value !== null && !Array.isArray(value);

const toRecord = (value: unknown): Record<string, unknown> => {
  if (isRecord(value)) {
    return value;
  }

  return {};
};

const toVariables = <TVariables>(value: unknown): TVariables => value as TVariables;

const toResultData = <TData>(value: unknown): TData => value as TData;

const toQueryKeyArray = (keys: ReadonlyArray<QueryKey> | undefined): QueryKey[] => {
  if (!keys || keys.length === 0) {
    return [...EMPTY_ARRAY];
  }

  return [...keys];
};

// =============================================================================
// HOOK IMPLEMENTATION
// =============================================================================

/**
 * useDLMutateQueryEngine
 *
 * Unified mutation hook that routes to Data Layer mutation hooks
 * based on the operation type.
 *
 * @typeParam TData - Result data type
 * @typeParam TVariables - Mutation variables type
 *
 * @example
 * ```tsx
 * // Create mutation
 * const { mutate } = useDLMutateQueryEngine({
 *   query: { operation: 'create', dimensions: [{ member: 'users.name' }] },
 *   onOptimistic: (vars) => ({
 *     ...vars,
 *     id: 'provisional-123',
 *     createdAt: new Date().toISOString(),
 *   }),
 * });
 *
 * mutate({ name: 'John', email: 'john@example.com' });
 *
 * // Update mutation
 * const { mutate: update } = useDLMutateQueryEngine({
 *   query: { operation: 'update', entityId: '123', dimensions: [{ member: 'users.name' }] },
 *   onOptimistic: (vars, prev) => ({ ...prev, ...vars }),
 *   getEntityId: (vars) => vars.id,
 * });
 *
 * update({ id: '123', name: 'Jane' });
 * ```
 */
export const useDLMutateQueryEngine = <TData = unknown, TVariables = unknown>(
  options: UseDLMutateQueryEngineOptions<TData, TVariables>,
): UseDLMutateQueryEngineResult<TData, TVariables> => {
  const {
    query,
    onOptimistic,
    getEntityId = defaultGetEntityId,
    invalidateKeys,
    onSuccess,
    onError,
    onSettled,
  } = options;

  // ─────────────────────────────────────────────────────────────────────────
  // DATA LAYER CONTEXT
  // ─────────────────────────────────────────────────────────────────────────

  const { isOnline, tableRegistry, queryClient } = useDataLayerInternals();

  // ─────────────────────────────────────────────────────────────────────────
  // ENGINE COMPONENTS (Singletons)
  // ─────────────────────────────────────────────────────────────────────────

  const tableExtractor = getTableExtractor();

  // ─────────────────────────────────────────────────────────────────────────
  // EXTRACT TABLE AND OPERATION
  // ─────────────────────────────────────────────────────────────────────────

  const extraction = useMemo(() => tableExtractor.extractDetailed(query), [tableExtractor, query]);

  const table = extraction.primaryTable ?? '';
  const operation: MutationOperation = resolveMutationOperation(query.operation);

  // ─────────────────────────────────────────────────────────────────────────
  // GET MUTATION DESCRIPTORS
  // ─────────────────────────────────────────────────────────────────────────

  const mutationRefs = useMemo(() => {
    if (!table) return null;
    return {
      create: getMutationReference(tableRegistry, table, MUTATION_OPERATIONS.CREATE),
      update: getMutationReference(tableRegistry, table, MUTATION_OPERATIONS.UPDATE),
      delete: getMutationReference(tableRegistry, table, MUTATION_OPERATIONS.DELETE),
    };
  }, [tableRegistry, table]);

  const fallbackMutationRef = useMemo(() => {
    if (table) {
      return getAnyMutationReference(tableRegistry, table);
    }
    return getAnyMutationReferenceFromRegistry(tableRegistry);
  }, [tableRegistry, table]);

  if (!fallbackMutationRef) {
    throw new Error(
      'useDLMutateQueryEngine requires at least one mutation API reference in the table registry',
    );
  }

  // List query key for optimistic updates
  const listQueryKey = useMemo(() => {
    if (!table) return undefined;
    return [table] as const;
  }, [table]);

  const mutationInvalidateKeys = useMemo(() => {
    const keys = toQueryKeyArray(invalidateKeys);
    if (!table) {
      return keys;
    }

    return [['query-engine', 'transactional', table] as const, ...keys];
  }, [invalidateKeys, table]);

  // ─────────────────────────────────────────────────────────────────────────
  // SHARED CALLBACKS
  // ─────────────────────────────────────────────────────────────────────────

  const handleSuccess = useCallback(
    async (data: unknown, vars: unknown) => {
      // Invalidate additional keys
      if (invalidateKeys && invalidateKeys.length > 0) {
        await Promise.all(
          invalidateKeys.map((key) => queryClient.invalidateQueries({ queryKey: key })),
        );
      }
      await onSuccess?.(toResultData<TData>(data), toVariables<TVariables>(vars));
    },
    [invalidateKeys, queryClient, onSuccess],
  );

  const handleError = useCallback(
    async (error: Error, vars: unknown) => {
      await onError?.(error, toVariables<TVariables>(vars));
    },
    [onError],
  );

  const handleSettled = useCallback(
    async (data: unknown, error: Error | null, vars: unknown) => {
      await onSettled?.(
        data === undefined ? undefined : toResultData<TData>(data),
        error,
        toVariables<TVariables>(vars),
      );
    },
    [onSettled],
  );

  // ─────────────────────────────────────────────────────────────────────────
  // CREATE MUTATION
  // ─────────────────────────────────────────────────────────────────────────

  const isCreateEnabled =
    operation === MUTATION_OPERATIONS.CREATE && mutationRefs?.create !== undefined;

  const createOptimistic = useCallback(
    (vars: unknown): unknown => {
      if (!onOptimistic) return vars;
      return onOptimistic(toVariables<TVariables>(vars), undefined);
    },
    [onOptimistic],
  );

  const createMutation = useDLCreate({
    mutation: mutationRefs?.create ?? fallbackMutationRef,
    table,
    onOptimistic: createOptimistic,
    listQueryKey: isCreateEnabled ? listQueryKey : undefined,
    invalidateKeys: mutationInvalidateKeys,
    onSuccess: handleSuccess,
    onError: handleError,
    onSettled: handleSettled,
  });

  // ─────────────────────────────────────────────────────────────────────────
  // UPDATE MUTATION
  // ─────────────────────────────────────────────────────────────────────────

  const isUpdateEnabled =
    operation === MUTATION_OPERATIONS.UPDATE && mutationRefs?.update !== undefined;

  const updateOptimistic = useCallback(
    (vars: unknown, prev: unknown): unknown => {
      if (!onOptimistic) {
        return { ...toRecord(prev), ...toRecord(vars) };
      }
      const previousData = prev === undefined ? undefined : toResultData<TData>(prev);
      return onOptimistic(toVariables<TVariables>(vars), previousData);
    },
    [onOptimistic],
  );

  const resolveEntityId = useCallback(
    (vars: unknown): string => getEntityId(toVariables<TVariables>(vars)),
    [getEntityId],
  );

  const updateMutation = useDLUpdate({
    mutation: mutationRefs?.update ?? fallbackMutationRef,
    table,
    getEntityId: resolveEntityId,
    onOptimistic: updateOptimistic,
    listQueryKey: isUpdateEnabled ? listQueryKey : undefined,
    invalidateKeys: mutationInvalidateKeys,
    onSuccess: handleSuccess,
    onError: handleError,
    onSettled: handleSettled,
  });

  // ─────────────────────────────────────────────────────────────────────────
  // DELETE MUTATION
  // ─────────────────────────────────────────────────────────────────────────

  const isDeleteEnabled =
    operation === MUTATION_OPERATIONS.DELETE && mutationRefs?.delete !== undefined;

  const deleteMutation = useDLDelete({
    mutation: mutationRefs?.delete ?? fallbackMutationRef,
    table,
    getEntityId: resolveEntityId,
    listQueryKey: isDeleteEnabled ? listQueryKey : undefined,
    invalidateKeys: mutationInvalidateKeys,
    onSuccess: handleSuccess,
    onError: handleError,
    onSettled: handleSettled,
  });

  // ─────────────────────────────────────────────────────────────────────────
  // SELECT ACTIVE MUTATION
  // ─────────────────────────────────────────────────────────────────────────

  const activeMutation = useMemo(() => {
    switch (operation) {
      case MUTATION_OPERATIONS.CREATE:
        return {
          mutation: createMutation,
          op: MUTATION_OPERATIONS.CREATE,
        };
      case MUTATION_OPERATIONS.UPDATE:
        return {
          mutation: updateMutation,
          op: MUTATION_OPERATIONS.UPDATE,
        };
      case MUTATION_OPERATIONS.DELETE:
        return {
          mutation: deleteMutation,
          op: MUTATION_OPERATIONS.DELETE,
        };
      default:
        return {
          mutation: createMutation,
          op: MUTATION_OPERATIONS.CREATE,
        };
    }
  }, [operation, createMutation, updateMutation, deleteMutation]);

  // ─────────────────────────────────────────────────────────────────────────
  // BUILD RESULT
  // ─────────────────────────────────────────────────────────────────────────

  const mut = activeMutation.mutation;

  // Create stable mutate function
  const mutate = useCallback(
    (variables: TVariables) => {
      mut.mutate(variables);
    },
    [mut],
  );

  // Create stable mutateAsync function
  const mutateAsync = useCallback(
    async (variables: TVariables): Promise<TData> => {
      const result = await mut.mutateAsync(variables);
      return toResultData<TData>(result);
    },
    [mut],
  );

  // Reset function
  const reset = useCallback(() => {
    mut.reset();
  }, [mut]);

  return {
    // Mutation functions
    mutate,
    mutateAsync,

    // Mutation state
    data: mut.data === undefined ? undefined : toResultData<TData>(mut.data),
    isPending: mut.isPending,
    isSuccess: mut.isSuccess,
    isError: mut.isError,
    isIdle: mut.isIdle,
    error: mut.error ?? null,

    // Offline status
    isQueued: mut.isQueued ?? false,
    isOffline: !isOnline,
    provisionalId: mut.provisionalId ?? null,

    // Execution info
    executionPath: EXECUTION_PATHS.TRANSACTIONAL,
    operation: activeMutation.op,
    table: table || null,

    // Actions
    reset,
  };
};
