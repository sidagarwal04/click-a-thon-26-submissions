/**
 * Public utility exports for data-layer consumers.
 *
 * @module utils
 */

export { buildQueryKey, getDataSource } from './query-key';

export { invalidateQueries, collectInvalidationKeys } from './mutation-helpers';

export {
  ERROR_SEVERITY,
  HOOK_CONTEXT,
  handleError,
  createScopedErrorHandler,
  type ErrorHandlerOptions,
} from './error-handler';
