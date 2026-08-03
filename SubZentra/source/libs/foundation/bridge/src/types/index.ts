/**
 * Type exports
 *
 * NOTE: Branded types (QueryId, WorkerId, SqlIdentifier, SqlTableName, Milliseconds, Timestamp)
 * should be imported directly from '@open-zentra/foundation-data-model'.
 *
 * NOTE: Const objects (BRIDGE_TYPE, PRIORITY, QUERY_MODE) from '../constants'; WORKER_STATUS from './pool'.
 * Types: BridgeType, PriorityLevel, QueryLockMode from '../constants'; WorkerStatus from './pool'.
 *
 * @module types
 */

export type {
  // Bridge types
  QueryOptions,
  ViewDefinition,
  TableInfo,
  ColumnInfo,
  QueryResult,
  DuckDBBridge,
  DuckDBBridgeStatus,
} from './bridge';

// WORKER_STATUS const (CAPITAL_SNAKE), WorkerStatus type (PascalCase)
export { WORKER_STATUS } from './pool';
export type { WorkerStatus } from './pool';

export type {
  QueryRequest,
  QueryItem,
  PoolQueryResult,
  WorkerInfo,
  DuckDBPoolConfig,
  ResolvedPoolConfig,
  PoolStatus,
  TableLockStatus,
} from './pool';
