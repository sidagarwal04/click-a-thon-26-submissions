/**
 * Cross-library contracts for foundation packages.
 *
 * @module contracts
 */

export {
  OPERATIONS,
  READ_OPERATIONS,
  WRITE_OPERATIONS,
  isOperation,
  isReadOperation,
  isWriteOperation,
  isMutationOperation,
  type Operation,
  type ReadOperation,
  type WriteOperation,
} from './operations';

export { DATA_FRESHNESS, type DataFreshnessLevel } from './analytics';

export { CONFLICT_RESOLUTION_TYPE, type ConflictResolutionType } from './conflict-resolution';

export type {
  ApiQueryDescriptor,
  ApiMutationDescriptor,
  UnifiedTableConfig,
  UnifiedTableApiConfig,
  UnifiedTableRealtimeConfig,
  UnifiedTableMergeConfig,
  TableAnalyticsConfig,
} from './table-config';
