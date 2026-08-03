/**
 * Shared Mutation Internals
 *
 * Provides common infrastructure for mutation hooks to reduce code duplication.
 * Used by useDLCreate, useDLUpdate, and useDLDelete.
 *
 * @module utils/use-mutation-internals
 */

import { useCallback, useMemo, useRef, useState } from 'react';

import { useQueryClient, type QueryClient, type QueryKey } from '@tanstack/react-query';
import type { AxiosInstance } from 'axios';

import type { WithId } from '@open-zentra/foundation-data-model';
import type { DatabaseFacade } from '@open-zentra/foundation-database';
import type { IQueueManager, SyncCoordinator } from '@open-zentra/foundation-sync-engine';

import { useDataLayerInternals } from '../provider/data-layer-internals-context';
import type { ErrorSeverityValue } from './error-handler';
import { collectInvalidationKeys, invalidateQueries } from './mutation-helpers';
import type { OptimisticContext, rollbackOptimisticUpdate } from './optimistic-updates';

// =============================================================================
// MUTATION INTERNALS
// =============================================================================

/**
 * Common mutation infrastructure returned by useMutationInternals
 */
export interface MutationInternals {
  /** TanStack Query client */
  readonly queryClient: QueryClient;
  /** Shared Axios instance */
  readonly axiosInstance: AxiosInstance;
  /** Database facade for cache operations */
  readonly database: DatabaseFacade;
  /** Sync coordinator for offline queue management */
  readonly syncCoordinator: SyncCoordinator;
  /** Whether the client is currently online */
  readonly isOnline: boolean;
  /** Memoized queue manager instance */
  readonly queueManager: IQueueManager;
}

/**
 * Hook to get common mutation dependencies
 *
 * Provides memoized access to query client, database, sync coordinator,
 * and queue manager. Reduces boilerplate in mutation hooks.
 *
 * @returns Common mutation infrastructure
 *
 * @example
 * ```ts
 * const { queryClient, database, queueManager, isOnline } = useMutationInternals();
 * ```
 */
export const useMutationInternals = (): MutationInternals => {
  const queryClient = useQueryClient();
  const { axiosInstance, database, syncCoordinator, isOnline } = useDataLayerInternals();

  // Memoize queue manager to avoid repeated access
  const queueManager = useMemo(() => syncCoordinator.getQueueManager(), [syncCoordinator]);

  return {
    queryClient,
    axiosInstance,
    database,
    syncCoordinator,
    isOnline,
    queueManager,
  };
};

// =============================================================================
// QUEUE STATE
// =============================================================================

/**
 * State management for mutation queue status
 */
export interface QueueState {
  /** Whether the mutation is queued for offline sync */
  readonly isQueued: boolean;
  /** Set the queued state */
  readonly setIsQueued: (value: boolean) => void;
}

/**
 * Hook for managing mutation queue state
 *
 * @returns Queue state and setter
 */
export const useQueueState = (): QueueState => {
  const [isQueued, setIsQueued] = useState(false);
  return { isQueued, setIsQueued };
};

// =============================================================================
// OPTIMISTIC CONTEXT REFS
// =============================================================================

/**
 * Configuration for optimistic context tracking
 */
export interface OptimisticContextRefs<TListData, TItemData> {
  /** Ref for list optimistic context */
  readonly listContextRef: React.MutableRefObject<OptimisticContext<TListData[]> | null>;
  /** Ref for item optimistic context */
  readonly itemContextRef: React.MutableRefObject<OptimisticContext<TItemData> | null>;
  /** Ref for entity ID tracking */
  readonly entityIdRef: React.MutableRefObject<string | null>;
  /** Clear all refs */
  readonly clearRefs: () => void;
}

/**
 * Hook for tracking optimistic update contexts
 *
 * Provides refs to store optimistic contexts for rollback on error.
 *
 * @returns Refs for optimistic context tracking
 */
export const useOptimisticContextRefs = <
  TListData extends WithId = WithId,
  TItemData = unknown,
>(): OptimisticContextRefs<TListData, TItemData> => {
  const listContextRef = useRef<OptimisticContext<TListData[]> | null>(null);
  const itemContextRef = useRef<OptimisticContext<TItemData> | null>(null);
  const entityIdRef = useRef<string | null>(null);

  const clearRefs = useCallback(() => {
    listContextRef.current = null;
    itemContextRef.current = null;
  }, []);

  return {
    listContextRef,
    itemContextRef,
    entityIdRef,
    clearRefs,
  };
};

// =============================================================================
// MUTATION CALLBACKS
// =============================================================================

/**
 * Options for creating mutation callbacks
 */
export interface MutationCallbackOptions<TData, TVariables> {
  /** Internals from useMutationInternals */
  readonly internals: MutationInternals;
  /** Keys to invalidate on success */
  readonly invalidateKeys: QueryKey[];
  /** Optional list query key */
  readonly listQueryKey?: QueryKey | undefined;
  /** Optional item query key generator */
  readonly itemQueryKey?: ((entityId: string) => QueryKey) | undefined;
  /** Entity ID ref for item invalidation */
  readonly entityIdRef: React.MutableRefObject<string | null>;
  /** User's onSuccess callback */
  readonly onSuccess?: ((data: TData, variables: TVariables) => void | Promise<void>) | undefined;
  /** User's onError callback */
  readonly onError?: ((error: Error, variables: TVariables) => void | Promise<void>) | undefined;
  /** User's onSettled callback */
  readonly onSettled?:
    | ((
        data: TData | undefined,
        error: Error | null,
        variables: TVariables,
      ) => void | Promise<void>)
    | undefined;
}

/**
 * Create standardized onSuccess callback for mutations
 *
 * Handles query invalidation and calls user callback.
 *
 * @param options - Callback options
 * @returns onSuccess callback function
 */
export const createOnSuccessCallback = <TData, TVariables>(
  options: Pick<
    MutationCallbackOptions<TData, TVariables>,
    'internals' | 'invalidateKeys' | 'listQueryKey' | 'itemQueryKey' | 'entityIdRef' | 'onSuccess'
  >,
): ((data: TData, variables: TVariables) => Promise<void>) => {
  const { internals, invalidateKeys, listQueryKey, itemQueryKey, entityIdRef, onSuccess } = options;

  return async (data: TData, variables: TVariables) => {
    // Invalidate related queries
    const keysToInvalidate = collectInvalidationKeys(
      invalidateKeys,
      listQueryKey,
      itemQueryKey,
      entityIdRef.current,
    );
    await invalidateQueries(internals.queryClient, keysToInvalidate);

    // Call user callback
    await onSuccess?.(data, variables);
  };
};

/**
 * Rollback utility function type
 */
type RollbackFn = typeof rollbackOptimisticUpdate;

/**
 * Error handler function type for scoped logging
 */
type ScopedErrorHandler = (
  error: unknown,
  options?: { severity?: ErrorSeverityValue; data?: Record<string, unknown> },
) => Error;

/**
 * Create standardized onError callback for mutations
 *
 * Handles optimistic rollback, scoped error logging, and calls user callback.
 *
 * @param options - Callback options including refs and rollback function
 * @returns onError callback function
 */
export const createOnErrorCallback = <TData, TVariables, TListData extends WithId, TItemData>(
  options: Pick<MutationCallbackOptions<TData, TVariables>, 'internals' | 'onError'> & {
    readonly listContextRef: React.MutableRefObject<OptimisticContext<TListData[]> | null>;
    readonly itemContextRef: React.MutableRefObject<OptimisticContext<TItemData> | null>;
    readonly rollbackFn: RollbackFn;
    /** Scoped error handler for logging */
    readonly errorHandler?: ScopedErrorHandler;
    /** Table name for error context */
    readonly table?: string;
    /** Additional error handling logic */
    readonly additionalErrorHandling?: (error: Error, variables: TVariables) => Promise<void>;
  },
): ((error: Error, variables: TVariables) => Promise<void>) => {
  const {
    internals,
    listContextRef,
    itemContextRef,
    rollbackFn,
    errorHandler,
    table,
    additionalErrorHandling,
    onError,
  } = options;

  return async (error: Error, variables: TVariables) => {
    // Log error with scoped handler if provided
    if (errorHandler) {
      if (table) {
        errorHandler(error, { severity: 'error', data: { table } });
      } else {
        errorHandler(error, { severity: 'error' });
      }
    }

    // Additional error handling (e.g., cache restoration)
    if (additionalErrorHandling) {
      await additionalErrorHandling(error, variables);
    }

    // Rollback optimistic updates
    if (listContextRef.current) {
      rollbackFn(internals.queryClient, listContextRef.current);
      listContextRef.current = null;
    }

    if (itemContextRef.current) {
      rollbackFn(internals.queryClient, itemContextRef.current);
      itemContextRef.current = null;
    }

    // Call user callback
    await onError?.(error, variables);
  };
};

/**
 * Create standardized onSettled callback for mutations
 *
 * Clears refs and calls user callback.
 *
 * @param options - Callback options
 * @returns onSettled callback function
 */
export const createOnSettledCallback = <TData, TVariables>(
  options: Pick<MutationCallbackOptions<TData, TVariables>, 'onSettled'> & {
    readonly clearRefs: () => void;
  },
): ((data: TData | undefined, error: Error | null, variables: TVariables) => Promise<void>) => {
  const { clearRefs, onSettled } = options;

  return async (data, error, variables) => {
    // Clear refs
    clearRefs();

    // Call user callback
    await onSettled?.(data, error, variables);
  };
};

// =============================================================================
// ID RESOLUTION
// =============================================================================

/**
 * Resolve entity ID using queue manager
 *
 * Converts provisional IDs to server IDs when available.
 *
 * @param queueManager - Queue manager instance
 * @param entityId - Original entity ID (may be provisional)
 * @returns Resolved server ID or original ID
 */
export const resolveEntityId = (queueManager: IQueueManager, entityId: string): string =>
  queueManager.resolveId(entityId);

/**
 * Prepare variables with resolved ID
 *
 * Updates variables with resolved server ID if different from original.
 *
 * @param variables - Original variables
 * @param originalId - Original entity ID
 * @param resolvedId - Resolved server ID
 * @returns Variables with resolved ID
 */
export const prepareResolvedVariables = <TVariables>(
  variables: TVariables,
  originalId: string,
  resolvedId: string,
): TVariables => {
  if (originalId === resolvedId) {
    return variables;
  }

  return {
    ...variables,
    id: resolvedId,
  };
};
