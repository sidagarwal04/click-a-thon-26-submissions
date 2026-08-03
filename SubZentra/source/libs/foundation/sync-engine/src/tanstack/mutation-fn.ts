/**
 * TanStack Mutation function creators with offline support
 * @module tanstack/mutation-fn
 */

import type { MutationFunction } from '@tanstack/react-query';

import {
  generateProvisionalId,
  MUTATION_TYPE,
  tryToJsonSerializable,
  type MutationType,
  type OfflineMutationResult,
  type QueryKeyBase,
} from '@open-zentra/foundation-data-model';
import { createDebugLogger, isNetworkError } from '@open-zentra/foundation-utils';

import type { NetworkStatusMonitor } from '../network/index';
import { getNetworkMonitor } from '../network/index';
import type { OfflineQueueManager } from '../queue/manager';
import { getQueueManager } from '../queue/manager';

/**
 * Offline mutation function configuration
 */
export interface OfflineMutationFnConfig<TData = unknown, TVariables = unknown> {
  /** Network monitor instance */
  networkMonitor?: NetworkStatusMonitor;
  /** Queue manager instance */
  queueManager?: OfflineQueueManager;
  /** Online mutation function */
  mutateFn: (variables: TVariables) => Promise<TData>;
  /** Mutation type */
  type: MutationType;
  /** Table/entity name */
  tableName: string;
  /** Extract entity ID from variables */
  getEntityId?: (variables: TVariables) => string;
  /** Create optimistic data for cache update */
  getOptimisticData?: (variables: TVariables) => TData | null;
  /** Query keys to invalidate on success */
  invalidateKeys?: QueryKeyBase[];
  /** Dependencies on other mutations */
  dependsOn?: string[];
  /** Enable debug logging */
  debug?: boolean;
}

// NOTE: OfflineMutationResult is now exported from @foundation/data-model
// Import it from there for consistency across the codebase

/**
 * Default configuration
 */
const DEFAULT_CONFIG = {
  debug: false,
};

const hasStringId = (value: unknown): value is { id: string } =>
  value !== null && typeof value === 'object' && 'id' in value && typeof value.id === 'string';

/**
 * Create an offline-aware mutation function
 */
export const createOfflineMutationFn = <TData = unknown, TVariables = unknown>(
  config: OfflineMutationFnConfig<TData, TVariables>,
): MutationFunction<OfflineMutationResult<TData>, TVariables> => {
  const {
    mutateFn,
    type,
    tableName,
    getEntityId,
    getOptimisticData,
    invalidateKeys,
    dependsOn,
    debug = DEFAULT_CONFIG.debug,
  } = config;

  const networkMonitor = config.networkMonitor ?? getNetworkMonitor();
  const queueManager = config.queueManager ?? getQueueManager();
  const logger = createDebugLogger('OfflineMutationFn', debug);

  return async (variables: TVariables): Promise<OfflineMutationResult<TData>> => {
    const entityId =
      getEntityId?.(variables) ?? (type === MUTATION_TYPE.CREATE ? generateProvisionalId() : '');
    const mutationId = crypto.randomUUID();
    const optimisticData = getOptimisticData?.(variables);
    const serializedPayload = tryToJsonSerializable(variables);
    const serializedOptimisticData =
      optimisticData === undefined ? undefined : tryToJsonSerializable(optimisticData);

    logger.debug('Mutation:', type, tableName, entityId);

    // If offline, queue the mutation
    if (!networkMonitor.isOnline) {
      logger.debug('Offline mode - queueing mutation');

      if (serializedPayload === null) {
        throw new Error('Offline queue payload must be JSON-serializable');
      }

      await queueManager.enqueue({
        type,
        tableName,
        entityId,
        payload: serializedPayload,
        optimisticData: serializedOptimisticData ?? undefined,
        invalidateKeys: invalidateKeys?.map((key) => JSON.stringify(key)),
        dependsOn,
      });

      return {
        data: optimisticData ?? null,
        isOffline: true,
        mutationId,
        entityId,
        queued: true,
      };
    }

    // Online mode - execute immediately
    try {
      logger.debug('Online mode - executing mutation');
      const data = await mutateFn(variables);

      return {
        data,
        isOffline: false,
        mutationId,
        entityId: hasStringId(data) ? data.id : entityId,
        queued: false,
      };
    } catch (error) {
      logger.debug('Mutation failed:', error);

      // If mutation fails due to network error, queue it
      if (isNetworkError(error)) {
        logger.debug('Network error - queueing mutation');

        if (serializedPayload === null) {
          throw new Error('Offline queue payload must be JSON-serializable');
        }

        await queueManager.enqueue({
          type,
          tableName,
          entityId,
          payload: serializedPayload,
          optimisticData: serializedOptimisticData ?? undefined,
          invalidateKeys: invalidateKeys?.map((key) => JSON.stringify(key)),
          dependsOn,
        });

        return {
          data: optimisticData ?? null,
          isOffline: true,
          mutationId,
          entityId,
          queued: true,
        };
      }

      throw error;
    }
  };
};

/**
 * Create a simple mutation function without offline queue
 * (for mutations that should fail if offline)
 */
export const createOnlineMutationFn = <TData = unknown, TVariables = unknown>(
  mutateFn: (variables: TVariables) => Promise<TData>,
  options?: { debug?: boolean },
): MutationFunction<TData, TVariables> => {
  const logger = createDebugLogger('OnlineMutationFn', options?.debug ?? false);

  return async (variables: TVariables): Promise<TData> => {
    const networkMonitor = getNetworkMonitor();

    if (!networkMonitor.isOnline) {
      throw new Error('This operation requires an internet connection');
    }

    logger.debug('Executing online mutation');
    return mutateFn(variables);
  };
};
