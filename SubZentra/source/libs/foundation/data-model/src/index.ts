/**
 * @foundation/data-model
 *
 * Core data model library containing schemas, types, query keys, and versioning.
 * This library has no dependencies and serves as the foundation for all data structures.
 *
 * @packageDocumentation
 */

import type { z } from 'zod';

import type { BaseEntitySchema as BaseEntitySchemaType } from './schemas/base.schema';
import type { EventSchema as EventSchemaType } from './schemas/event.schema';
import type { SessionSchema as SessionSchemaType } from './schemas/session.schema';

// ============================================================================
// Base Schemas (common building blocks)
// ============================================================================

export {
  BaseEntitySchema,
  TenantScopedSchema,
  SoftDeleteSchema,
  TimestampsSchema,
  PaginationParamsSchema,
  SortDirectionSchema,
  DateRangeSchema,
  PROVISIONAL_ID_PREFIX,
  isProvisionalId,
  generateProvisionalId,
} from './schemas/base.schema';

// ============================================================================
// Entity Schemas
// ============================================================================

export {
  SessionSchema,
  SessionStatusSchema,
  SessionFiltersSchema,
  SessionSummarySchema,
  SessionMetricsSchema,
  LandingPageSchema,
  ExitPageSchema,
  CreateSessionSchema,
  UpdateSessionSchema,
} from './schemas/session.schema';

export {
  EventSchema,
  EventTypeSchema,
  DeviceTypeSchema,
  BrowserInfoSchema,
  DeviceInfoSchema,
  GeoLocationSchema,
  PageContextSchema,
  UtmParamsSchema,
  CreateEventSchema,
  EventFiltersSchema,
} from './schemas/event.schema';

// ============================================================================
// Types (used by sync-engine, database, data-layer)
// ============================================================================

// Type-only exports (no runtime value)
export type {
  IdMapping,
  UserRole,
  UserPermissions,
  JsonPrimitive,
  JsonObject,
  JsonArray,
  JsonValue,
  JsonSerializable,
  Brand,
  // Validation result data interface (the data type for ValidationResult utilities)
  ValidationResultData,
  // Data source types (used by data-layer, sync-engine)
  DataSource,
  OfflineDataSource,
  OfflineMetadata,
  WithOfflineMetadata,
  // Shared database contracts
  QueryCacheStatus,
  MutationStatus,
  MutationType,
  MutationQueueEntry,
  CreateMutationOptions,
  OpfsFileType,
  SyncStateKey,
  DatabaseTransactionMode,
  DatabaseTransactionTable,
  DuckDBViewDefinition,
  DuckDBViewsValue,
  LastSyncValue,
  TableSyncMetadataEntry,
} from './types';
// Value exports (includes their associated types automatically)
// Result, Milliseconds, Timestamp, and ID constructors are both types and value constructors
export {
  isJsonSerializable,
  cloneJsonSerializable,
  toJsonSerializable,
  tryToJsonSerializable,
  assertJsonSerializable,
  JsonSerializationError,
  DATA_SOURCE,
  OFFLINE_DATA_SOURCE,
  Result,
  Milliseconds,
  Timestamp,
  MutationId,
  EntityId,
  TabId,
  ProvisionalId,
  // Bridge branded constructors
  QueryId,
  WorkerId,
  SqlTableName,
  SqlIdentifier,
  // Query engine branded constructors
  MemberRef,
  ExecutionId,
} from './types';

// Sync-related types (used by sync-engine, data-layer)
export type {
  ConflictContext,
  ConflictResult,
  ConflictStrategy,
  ConflictWinner,
  MergeConfig,
  QueueStats,
  ProcessingResult,
  SyncState,
  SyncEventType,
  // Network types
  NetworkStatus,
  NetworkStatusListener,
  // Cross-tab types
  CrossTabMessageType,
  CrossTabMessagePayload,
  CrossTabMessage,
  CrossTabMessageHandler,
  // Sync event types
  SyncEvent,
  SyncEventListener,
  // Query types
  OfflineQuerySource,
  OfflineQueryContext,
  // Mutation types
  OfflineMutationResult,
  // Type constraints
  ConflictResolvableData,
  RealtimeApplyStrategy,
  RealtimeOwnershipState,
  RealtimeConnectionState,
  RealtimeSubscriptionState,
  RealtimeDataKind,
  RealtimeClientMessageType,
  RealtimeServerMessageType,
  RealtimeTopicDescriptor,
  RealtimeTopicCursor,
  RealtimeCursorStore,
  RealtimeConnectionSnapshot,
  RealtimeSubscriptionSnapshot,
  RealtimeSubscriptionMap,
  RealtimeHelloClientMessage,
  RealtimeResumeClientMessage,
  RealtimeSubscribeClientMessage,
  RealtimeUnsubscribeClientMessage,
  RealtimeAckClientMessage,
  RealtimePingClientMessage,
  RealtimePongClientMessage,
  RealtimeClientMessage,
  RealtimeHelloAckServerMessage,
  RealtimeSubscribedServerMessage,
  RealtimeUnsubscribedServerMessage,
  RealtimeEventServerMessage,
  RealtimeSnapshotServerMessage,
  RealtimeResyncRequiredServerMessage,
  RealtimeErrorServerMessage,
  RealtimePingServerMessage,
  RealtimePongServerMessage,
  RealtimeServerMessage,
  RealtimeDataServerMessage,
  RealtimeAckServerMessage,
  RealtimeRuntimeState,
  RealtimeProtocolVersion,
  RealtimeCapability,
  RealtimeCapabilityMap,
  RealtimeMessageId,
  RealtimeRequestId,
  RealtimeSchema,
} from './types';
// Sync-related constants (value + type exports)
export {
  CONFLICT_STRATEGY,
  CONFLICT_WINNER,
  SYNC_EVENT_TYPE,
  CROSS_TAB_MESSAGE_TYPE,
  OFFLINE_QUERY_SOURCE,
  REALTIME_APPLY_STRATEGY,
  REALTIME_OWNERSHIP_STATE,
  REALTIME_CONNECTION_STATE,
  REALTIME_SUBSCRIPTION_STATE,
  REALTIME_DATA_KIND,
  REALTIME_CLIENT_MESSAGE_TYPE,
  REALTIME_SERVER_MESSAGE_TYPE,
  realtimeTopicDescriptorSchema,
  realtimeTopicCursorSchema,
  realtimeCursorStoreSchema,
  realtimeConnectionSnapshotSchema,
  realtimeSubscriptionSnapshotSchema,
  realtimeSubscriptionMapSchema,
  realtimeHelloClientMessageSchema,
  realtimeResumeClientMessageSchema,
  realtimeSubscribeClientMessageSchema,
  realtimeUnsubscribeClientMessageSchema,
  realtimeAckClientMessageSchema,
  realtimePingClientMessageSchema,
  realtimePongClientMessageSchema,
  realtimeClientMessageSchema,
  realtimeHelloAckServerMessageSchema,
  realtimeSubscribedServerMessageSchema,
  realtimeUnsubscribedServerMessageSchema,
  realtimeEventServerMessageSchema,
  realtimeSnapshotServerMessageSchema,
  realtimeResyncRequiredServerMessageSchema,
  realtimeErrorServerMessageSchema,
  realtimePingServerMessageSchema,
  realtimePongServerMessageSchema,
  realtimeServerMessageSchema,
  isRealtimeDataServerMessage,
  isRealtimeAckServerMessage,
  parseRealtimeClientMessage,
  parseRealtimeServerMessage,
  safeParseRealtimeClientMessage,
  safeParseRealtimeServerMessage,
  // Database constants and helpers
  QUERY_CACHE_STATUS,
  MUTATION_STATUS,
  MUTATION_TYPE,
  OPFS_FILE_TYPE,
  SYNC_STATE_KEY,
  DATABASE_TRANSACTION_MODE,
  DATABASE_TRANSACTION_TABLE,
  createTableSyncMetadataEntry,
  needsTableUpdate,
  getFilesNeedingDownload,
} from './types';

// Utility types (general-purpose type transformations)
export type {
  DeepReadonly,
  DeepPartial,
  RequireFields,
  OptionalFields,
  KeysOfType,
  Mutable,
  DeepMutable,
  NonNullableFields,
  NullableFields,
  PickByType,
  OmitByType,
  ValueOf,
  ArrayElement,
  // Entity ID types
  WithId,
  WithRequiredId,
  ExtractId,
  PartialBy,
} from './types';

// Inferred types from schemas
export type Session = z.infer<typeof SessionSchemaType>;
export type Event = z.infer<typeof EventSchemaType>;
export type BaseEntity = z.infer<typeof BaseEntitySchemaType>;

// ============================================================================
// Query Keys (used by data-layer, sync-engine, database)
// ============================================================================

export type {
  QueryKeyBase,
  EntityQueryKeyFactory,
  AnalyticsQueryKey,
  QueryKeyMeta,
  ApiEndpointPath,
  ApiEndpointRef,
} from './query-keys';

export {
  hashQueryKey,
  createQueryKeys,
  createAnalyticsQueryKey,
  extractQueryKeyMeta,
  matchesQueryKey,
  QUERY_SCOPE,
} from './query-keys';

// ============================================================================
// Cross-library contracts (used by data-layer and query-engine)
// ============================================================================

export {
  OPERATIONS,
  READ_OPERATIONS,
  WRITE_OPERATIONS,
  isOperation,
  isReadOperation,
  isWriteOperation,
  isMutationOperation,
  DATA_FRESHNESS,
  CONFLICT_RESOLUTION_TYPE,
} from './contracts';

export type {
  ApiQueryDescriptor,
  ApiMutationDescriptor,
  Operation,
  ReadOperation,
  WriteOperation,
  DataFreshnessLevel,
  ConflictResolutionType,
  UnifiedTableConfig,
  UnifiedTableApiConfig,
  UnifiedTableRealtimeConfig,
  UnifiedTableMergeConfig,
  TableAnalyticsConfig,
} from './contracts';

// ============================================================================
// Datasource contracts (used by data-layer and query-engine)
// ============================================================================

export type {
  DataSourceFileInfo,
  DataSourceTableInfo,
  DataSourceMetadata,
  DataSourceResponse,
  DataSourceRequest,
} from './datasource';

export {
  isDataSourceFileInfo,
  isDataSourceTableInfo,
  isDataSourceResponse,
  calculateTableSize,
  calculateTotalRows,
  calculateTotalSize,
  getTablesNeedingUpdate,
  hasExpiredUrls,
} from './datasource';

// ============================================================================
// Versioning (used by data-layer, sync-engine)
// ============================================================================

export { SCHEMA_VERSION } from './versioning';

// ============================================================================
// Validation Types
// ============================================================================

export type { ValidationSeverity, ValidationIssue } from './types';
export { VALIDATION_SEVERITY, ValidationResult, BrandedTypeValidationError } from './types';

// ============================================================================
// Type Guards
// ============================================================================

export {
  isArrowVector,
  isArrowTable,
  isArrowField,
  isMap,
  isSet,
  isPlainObject,
  isObject,
  isNonEmptyString,
  // Entity ID type guards
  hasId,
  hasAnyId,
  getEntityId,
  matchesEntityId,
  toNumber,
  toString,
  toBoolean,
  toDateIsoString,
  toDate,
  ARROW_TYPE_ID,
  convertArrowValueSafe,
  convertArrowRow,
} from './types';

// ============================================================================
// Error Infrastructure
// ============================================================================

export {
  // Error codes
  FOUNDATION_ERROR_CODE,
  ERROR_CATEGORY,
  getErrorCategory,
  isRetryableErrorCode,
  // Error classes
  FoundationError,
  GenericFoundationError,
  toFoundationError,
  isFoundationError,
  hasErrorCode,
  isErrorCategory,
  // Error callbacks
  createErrorInfo,
  adaptLegacyCallback,
  adaptToLegacyCallback,
  noopErrorCallback,
  createConsoleErrorCallback,
  combineErrorCallbacks,
  filterByCategory,
  filterByCode,
  // Query execution errors
  QueryTimeoutError,
  QueryCancelledError,
  QueryExecutionError,
  CANCELLATION_REASON,
} from './errors';

export type {
  FoundationErrorCode,
  ErrorCategory,
  SerializedError,
  ErrorContext,
  ErrorInfo,
  FoundationErrorCallback,
  LegacyErrorCallback,
  CancellationReasonKind,
} from './errors';

// ============================================================================
// HTTP Constants (shared across foundation-http, foundation-metrics)
// ============================================================================

export { HTTP_METHOD, type HttpMethod } from './http';

// ============================================================================
// Observability Constants (shared across foundation-metrics, foundation-http)
// ============================================================================

export {
  ENVIRONMENT,
  type Environment,
  COMPLIANCE_REGION,
  type ComplianceRegion,
  SEVERITY_NUMBER,
  type SeverityNumberValue,
  HASH_ALGORITHM,
  type HashAlgorithm,
} from './observability-constants';
