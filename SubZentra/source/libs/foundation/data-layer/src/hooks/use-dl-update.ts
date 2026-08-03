/**
 * useDLUpdate - Update mutation with optimistic updates
 *
 * @module hooks/use-dl-update
 */

import { useCallback } from 'react';

import { useMutation, type QueryKey } from '@tanstack/react-query';

import { toJsonSerializable, type ApiMutationDescriptor } from '@open-zentra/foundation-data-model';
import type { WithId } from '@open-zentra/foundation-data-model';

import { executeMutationDescriptor } from '../core/http-descriptor';
import type {
  BaseMutationOptions,
  DLMutationResult,
  MutationDescriptorArgs,
  MutationDescriptorData,
} from '../core/types';
import { createScopedErrorHandler } from '../utils/error-handler';
import {
  buildMutationResult,
  executeLocalFirstMutation,
  persistToCache,
} from '../utils/mutation-helpers';
import {
  optimisticUpdateInList,
  optimisticUpdateItem,
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

const handleUpdateError = createScopedErrorHandler('useDLUpdate');

export interface UseDLUpdateOptions<
  TMutation extends ApiMutationDescriptor,
  TData = MutationDescriptorData<TMutation>,
  TVariables extends MutationDescriptorArgs<TMutation> = MutationDescriptorArgs<TMutation>,
> extends BaseMutationOptions<TMutation, TData, TVariables> {
  readonly onOptimistic: (variables: TVariables, previousData?: TData) => TData;
  readonly getEntityId: (variables: TVariables) => string;
  readonly itemQueryKey?: (entityId: string) => QueryKey;
  readonly listQueryKey?: QueryKey;
}

export const useDLUpdate = <
  TMutation extends ApiMutationDescriptor,
  TData = MutationDescriptorData<TMutation>,
  TVariables extends MutationDescriptorArgs<TMutation> = MutationDescriptorArgs<TMutation>,
>(
  options: UseDLUpdateOptions<TMutation, TData, TVariables>,
): DLMutationResult<TData, TVariables> => {
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
    onOptimistic,
    listQueryKey,
    itemQueryKey,
    invalidateKeys = [],
    onSuccess,
    onError,
    onSettled,
  } = options;

  const mutationFn = useCallback(
    async (variables: TVariables): Promise<TData> => {
      const entityId = getEntityId(variables);
      entityIdRef.current = entityId;

      const resolvedId = resolveEntityId(queueManager, entityId);

      const currentItemKey = itemQueryKey?.(resolvedId);
      const currentData = currentItemKey
        ? queryClient.getQueryData<TData>(currentItemKey)
        : undefined;

      const optimisticData = onOptimistic(variables, currentData);

      if (listQueryKey) {
        listContextRef.current = optimisticUpdateInList<WithId>(
          queryClient,
          listQueryKey,
          resolvedId,
          (item) => ({ ...item, ...(optimisticData as object) }),
        );
      }

      if (currentItemKey) {
        itemContextRef.current = optimisticUpdateItem<TData>(
          queryClient,
          currentItemKey,
          () => optimisticData,
        );
      }

      await persistToCache(database, table, resolvedId, optimisticData, true);

      return executeLocalFirstMutation<TData>({
        isOnline,
        setIsQueued,
        offlineResult: optimisticData,
        queueOffline: async () => {
          await queueManager.enqueue({
            type: 'update',
            tableName: table,
            entityId: resolvedId,
            payload: toJsonSerializable(variables),
            optimisticData: toJsonSerializable(optimisticData),
            invalidateKeys: invalidateKeys.map((key) => JSON.stringify(key)),
          });
        },
        executeOnline: async () => {
          const resolvedVariables = prepareResolvedVariables(variables, entityId, resolvedId);
          return (await executeMutationDescriptor(
            axiosInstance,
            mutation,
            resolvedVariables,
          )) as TData;
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
    itemQueryKey,
    entityIdRef,
    onSuccess,
  });

  const handleSettled = createOnSettledCallback({
    clearRefs,
    onSettled,
  });

  // eslint-disable-next-line react-hooks/refs -- ref objects passed, read only inside the error callback
  const handleError = createOnErrorCallback<TData, TVariables, WithId, TData>({
    internals,
    listContextRef,
    itemContextRef,
    rollbackFn: rollbackOptimisticUpdate,
    errorHandler: handleUpdateError,
    table,
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
    provisionalId: null,
    isOffline: !isOnline,
  });
};
