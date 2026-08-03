/**
 * Query key exports
 * @module query-keys
 */

// Types
export type {
  QueryKeyBase,
  EntityQueryKey,
  AnalyticsQueryKey,
  QueryScope,
  EntityQueryKeyFactory,
  QueryHash,
  QueryKeyMeta,
  EntityTableName,
  ApiEndpointPath,
  ApiEndpointRef,
} from './types';

export { TABLE_NAMES, QUERY_SCOPE } from './types';

// Factory functions
export {
  createQueryKeys,
  createAnalyticsQueryKey,
  extractQueryKeyMeta,
  hashQueryKey,
  matchesQueryKey,
} from './factory';

// Pre-defined key factories
export {
  userKeys,
  eventKeys,
  sessionKeys,
  tenantKeys,
  projectKeys,
  dashboardKeys,
  reportKeys,
} from './factory';
