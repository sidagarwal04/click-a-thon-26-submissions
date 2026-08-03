/**
 * Queue exports
 *
 * NOTE: QueueStats and ProcessingResult types should be imported
 * directly from @open-zentra/foundation-data-model
 *
 * @module queue
 */

export {
  OfflineQueueManager,
  getQueueManager,
  resetQueueManager,
  hasQueueManager,
  createQueueManager,
  type QueueManagerConfig,
} from './manager';

export {
  QueueProcessor,
  createQueueProcessor,
  type MutationExecutor,
  type MutationExecutorResult,
  type QueueProcessorConfig,
} from './processor';
