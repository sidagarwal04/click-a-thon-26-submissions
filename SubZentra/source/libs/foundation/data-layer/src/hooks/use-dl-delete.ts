/**
 * useDLDelete - Delete mutation with optimistic removal
 *
 * @module hooks/use-dl-delete
 */

import { useCallback } from 'react';

import { useMutation, type QueryKey } from '@tanstack/react-query';

import {
  hashQueryKey,
  SCHEMA_VERSION,
  toJsonSerializable,
  type ApiMutationDescriptor,
} from '@open-zentra/foundation-data-model';
import type { WithId } from '@open-zentra/foundation-data-model';
import { createCacheEntry } from '@open-zentra/foundation-database';

import { executeMutationDescriptor } from '../core/http-descriptor';
import { DEFAULT_CACHE_TTL } from '../core/constants';
import type {
  BaseMutationOptions,
  DLMutationResult,
  MutationDescriptorArgs,
  MutationDescriptorData,
} from '../core/types';
import { createScopedErrorHandler } from '../utils/error-handler';
import {
  buildMutationResult,
  deleteFromCache,
  executeLocalFirstMutation,
} from '../utils/mutation-helpers';
import {
  createOptimisticContext,
  optimisticRemoveFromList,
  rollbackOptimisticUpdate,
} from '../utils/optimistic-updates';
import {
  createOnErrorCallback,
  createOnSettledCallback,
  createOnSuccessCallback,
  prepareResolvedVariables,
  resolveEntityId,
  useMutationInternals,
  useOptimisticContextRefs,
  useQueueState,
} from '../utils/use-mutation-internals';

const handleDeleteError = createScopedErrorHandler('useDLDelete');

export interface UseDLDeleteOptions<
  TMutation extends ApiMutationDescriptor,
  TData = MutationDescriptorData<TMutation>,
  TVariables extends MutationDescriptorArgs<TMutation> = MutationDescriptorArgs<TMutation>,
> extends BaseMutationOptions<TMutation, TData, TVariables> {
  readonly getEntityId: (variables: TVariables) => string;
  readonly itemQueryKey?: (entityId: string) => QueryKey;
  readonly listQueryKey?: QueryKey;
}

export const useDLDelete = <
  TMutation extends ApiMutationDescriptor,
  TData = MutationDescriptorData<TMutation>,
  TVariables extends MutationDescriptorArgs<TMutation> = MutationDescriptorArgs<TMutation>,
>(
  options: UseDLDeleteOptions<TMutation, TData, TVariables>,
): DLMutationResult<TData | undefined, TVariables> => {
  const internals = useMutationInternals();
  const { queryClient, database, queueManager, isOnline, axiosInstance } = internals;
  const { isQueued, setIsQueued } = useQueueState();
  const { listContextRef, itemContextRef, entityIdRef, clearRefs } = useOptimisticContextRefs<
    WithId,
    TData
  >();

  const {
    mutation,
    table,
    getEntityId,
    listQueryKey,
    itemQueryKey,
    invalidateKeys = [],
    onSuccess,
    onError,
    onSettled,
  } = options;

  const mutationFn = useCallback(
    async (variables: TVariables): Promise<TData | undefined> => {
      const entityId = getEntityId(variables);
      entityIdRef.current = entityId;

      const resolvedId = resolveEntityId(queueManager, entityId);

      if (listQueryKey) {
        listContextRef.current = optimisticRemoveFromList<WithId>(
          queryClient,
          listQueryKey,
          resolvedId,
        );
      }

      if (itemQueryKey) {
        const currentItemKey = itemQueryKey(resolvedId);
        itemContextRef.current = createOptimisticContext<TData>(queryClient, currentItemKey);
        queryClient.removeQueries({ queryKey: currentItemKey });
      }

      await deleteFromCache(database, table, resolvedId);

      return executeLocalFirstMutation<TData | undefined>({
        isOnline,
        setIsQueued,
        offlineResult: undefined,
        queueOffline: async () => {
          await queueManager.enqueue({
            type: 'delete',
            tableName: table,
            entityId: resolvedId,
            payload: toJsonSerializable(variables),
            invalidateKeys: invalidateKeys.map((key) => JSON.stringify(key)),
          });
        },
        executeOnline: async () => {
          const resolvedVariables = prepareResolvedVariables(variables, entityId, resolvedId);
          return (await executeMutationDescriptor(
            axiosInstance,
            mutation,
            resolvedVariables,
          )) as TData | undefined;
        },
      });
    },
    [
      axiosInstance,
      database,
      entityIdRef,
      getEntityId,
      invalidateKeys,
      isOnline,
      itemContextRef,
      itemQueryKey,
      listContextRef,
      listQueryKey,
      mutation,
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
    entityIdRef,
    onSuccess,
  });

  const handleSettled = createOnSettledCallback({
    clearRefs,
    onSettled,
  });

  const restoreCacheOnError = async (): Promise<void> => {
    const prevData = itemContextRef.current?.previousData;
    if (prevData && entityIdRef.current) {
      const cacheKey = hashQueryKey([table, entityIdRef.current]);
      const entry = createCacheEntry(
        cacheKey,
        [table, entityIdRef.current],
        toJsonSerializable(prevData),
        {
          tableName: table,
          ttl: DEFAULT_CACHE_TTL,
          schemaVersion: SCHEMA_VERSION,
          isOfflineData: true,
        },
      );
      await database.queries.set(entry);
    }
  };

  // eslint-disable-next-line react-hooks/refs -- ref objects passed, read only inside the error callback
  const handleError = createOnErrorCallback<TData, TVariables, WithId, TData>({
    internals,
    listContextRef,
    itemContextRef,
    rollbackFn: rollbackOptimisticUpdate,
    errorHandler: handleDeleteError,
    table,
    additionalErrorHandling: restoreCacheOnError,
    onError,
  });

  const mutationResult = useMutation<TData | undefined, Error, TVariables>({
    mutationFn,
    onSuccess: handleSuccess,
    onError: handleError,
    onSettled: handleSettled,
  });

  return buildMutationResult({
    mutationResult,
    isQueued,
    provisionalId: null,
    isOffline: !isOnline,
  });
};
