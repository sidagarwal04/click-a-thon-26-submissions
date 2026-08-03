/**
 * TanStack Query helpers exports
 *
 * NOTE: OfflineQueryContext and OfflineMutationResult types should be imported
 * directly from @open-zentra/foundation-data-model
 *
 * @module tanstack
 */

export {
  createOfflineQueryFn,
  createOfflineQueryFnWithContext,
  type OfflineQueryFnConfig,
} from './query-fn';

export {
  createOfflineMutationFn,
  createOnlineMutationFn,
  type OfflineMutationFnConfig,
} from './mutation-fn';
