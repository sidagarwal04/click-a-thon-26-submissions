/**
 * useDLCreate - Create mutation with local-first optimistic updates
 *
 * @module hooks/use-dl-create
 */

import { useCallback, useRef, useState } from 'react';

import { useMutation, type QueryKey } from '@tanstack/react-query';

import {
  generateProvisionalId,
  hashQueryKey,
  SCHEMA_VERSION,
  toJsonSerializable,
  type ApiMutationDescriptor,
} from '@open-zentra/foundation-data-model';
import type { WithId } from '@open-zentra/foundation-data-model';
import { createCacheEntry } from '@open-zentra/foundation-database';

import { executeMutationDescriptor } from '../core/http-descriptor';
import type {
  BaseMutationOptions,
  DLMutationResult,
  MutationDescriptorArgs,
  MutationDescriptorData,
} from '../core/types';
import { DEFAULT_CACHE_TTL } from '../core/constants';
import { createScopedErrorHandler } from '../utils/error-handler';
import { buildMutationResult, executeLocalFirstMutation } from '../utils/mutation-helpers';
import {
  optimisticAddToList,
  replaceProvisionalId,
  type OptimisticContext,
} from '../utils/optimistic-updates';
import {
  createOnErrorCallback,
  createOnSettledCallback,
  createOnSuccessCallback,
  useMutationInternals,
  useQueueState,
} from '../utils/use-mutation-internals';

const handleCreateError = createScopedErrorHandler('useDLCreate');

const isRecord = (value: unknown): value is Record<string, unknown> =>
  value !== null && typeof value === 'object' && !Array.isArray(value);

const getResultEntityId = (result: unknown): string | null =>
  isRecord(result) && typeof result.id === 'string' ? result.id : null;

export interface UseDLCreateOptions<
  TMutation extends ApiMutationDescriptor,
  TData = MutationDescriptorData<TMutation>,
  TVariables extends MutationDescriptorArgs<TMutation> = MutationDescriptorArgs<TMutation>,
> extends BaseMutationOptions<TMutation, TData, TVariables> {
  readonly onOptimistic: (variables: TVariables) => TData;
  readonly listQueryKey?: QueryKey;
}

export const useDLCreate = <
  TMutation extends ApiMutationDescriptor,
  TData = MutationDescriptorData<TMutation>,
  TVariables extends MutationDescriptorArgs<TMutation> = MutationDescriptorArgs<TMutation>,
>(
  options: UseDLCreateOptions<TMutation, TData, TVariables>,
): DLMutationResult<TData, TVariables> => {
  const internals = useMutationInternals();
  const { queryClient, database, queueManager, isOnline, axiosInstance } = internals;
  const { isQueued, setIsQueued } = useQueueState();

  const optimisticContextRef = useRef<OptimisticContext<WithId[]> | null>(null);
  const [provisionalId, setProvisionalId] = useState<string | null>(null);
  const provisionalIdRef = useRef<string | null>(null);

  const {
    mutation,
    table,
    onOptimistic,
    listQueryKey,
    invalidateKeys = [],
    onSuccess,
    onError,
    onSettled,
  } = options;

  const mutationFn = useCallback(
    async (variables: TVariables): Promise<TData> => {
      const newProvisionalId = generateProvisionalId();
      setProvisionalId(newProvisionalId);
      provisionalIdRef.current = newProvisionalId;

      const optimisticData = onOptimistic(variables);
      if (!isRecord(optimisticData)) {
        throw new Error('useDLCreate.onOptimistic must return an object-like value');
      }

      const optimisticWithId = {
        ...optimisticData,
        id: newProvisionalId,
        _isPendingSync: true,
        _provisionalId: newProvisionalId,
        _createdLocallyAt: Date.now(),
      };

      if (listQueryKey) {
        optimisticContextRef.current = optimisticAddToList(
          queryClient,
          listQueryKey,
          optimisticWithId,
        );
      }

      const cacheKey = hashQueryKey([table, newProvisionalId]);
      const serializedData = toJsonSerializable(optimisticWithId);
      const entry = createCacheEntry(cacheKey, [table, newProvisionalId], serializedData, {
        tableName: table,
        ttl: DEFAULT_CACHE_TTL,
        schemaVersion: SCHEMA_VERSION,
        isOfflineData: true,
      });
      await database.queries.set(entry);

      return executeLocalFirstMutation<TData>({
        isOnline,
        setIsQueued,
        offlineResult: optimisticWithId as TData,
        queueOffline: async () => {
          await queueManager.enqueue({
            type: 'create',
            tableName: table,
            entityId: newProvisionalId,
            payload: toJsonSerializable(variables),
            optimisticData: serializedData,
            invalidateKeys: invalidateKeys.map((key) => JSON.stringify(key)),
          });
        },
        executeOnline: async () => {
          const result = (await executeMutationDescriptor(
            axiosInstance,
            mutation,
            variables,
          )) as TData;
          const serverId = getResultEntityId(result) ?? newProvisionalId;

          if (serverId !== newProvisionalId) {
            const finalData = {
              ...(result as object),
              _isPendingSync: false,
              _provisionalId: undefined,
              _createdLocallyAt: undefined,
            };
            const serverCacheKey = hashQueryKey([table, serverId]);
            const serverEntry = createCacheEntry(
              serverCacheKey,
              [table, serverId],
              toJsonSerializable(finalData),
              {
                tableName: table,
                ttl: DEFAULT_CACHE_TTL,
                schemaVersion: SCHEMA_VERSION,
                isOfflineData: false,
              },
            );
            await database.queries.set(serverEntry);
            await database.queries.delete(cacheKey);

            if (listQueryKey) {
              replaceProvisionalId(queryClient, listQueryKey, newProvisionalId, serverId);
            }
          }

          return result;
        },
      });
    },
    [
      axiosInstance,
      database,
      invalidateKeys,
      isOnline,
      listQueryKey,
      mutation,
      onOptimistic,
      queryClient,
      queueManager,
      setIsQueued,
      table,
    ],
  );

  // The factory stores the ref object and reads `.current` inside the callback
  // it returns, which React Query invokes after the mutation settles. Nothing
  // is read during render, so the value cannot be stale in the rendered output.
  // eslint-disable-next-line react-hooks/refs -- ref object passed, never read during render
  const handleSuccess = createOnSuccessCallback({
    internals,
    invalidateKeys,
    listQueryKey,
    entityIdRef: provisionalIdRef,
    onSuccess,
  });

  const clearRefs = useCallback(() => {
    optimisticContextRef.current = null;
  }, []);

  // eslint-disable-next-line react-hooks/refs -- clearRefs writes the ref when React Query settles, not during render
  const handleSettled = createOnSettledCallback({
    clearRefs,
    onSettled,
  });

  const dummyItemContextRef = useRef<null>(null);

  const cleanupOnError = async (): Promise<void> => {
    const currentProvisionalId = provisionalIdRef.current;
    if (currentProvisionalId && !isQueued) {
      const cacheKey = hashQueryKey([table, currentProvisionalId]);
      await database.queries.delete(cacheKey);
    }
  };

  // eslint-disable-next-line react-hooks/refs -- ref objects passed, read only inside the error callback
  const handleError = createOnErrorCallback<TData, TVariables, WithId, null>({
    internals,
    listContextRef: optimisticContextRef,
    itemContextRef: dummyItemContextRef,
    rollbackFn: () => undefined,
    errorHandler: handleCreateError,
    table,
    additionalErrorHandling: cleanupOnError,
    onError,
  });

  const mutationResult = useMutation<TData, Error, TVariables>({
    mutationFn,
    onSuccess: handleSuccess,
    onError: handleError,
    onSettled: handleSettled,
  });

  return buildMutationResult({
    mutationResult,
    isQueued,
    provisionalId,
    isOffline: !isOnline,
  });
};
