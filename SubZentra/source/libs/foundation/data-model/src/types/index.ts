/**
 * Type exports
 * @module types
 */

// Base types
export type {
  Timestamps,
  BaseEntity,
  SoftDelete,
  TenantScoped,
  PaginationParams,
  SortDirection,
  DateRange,
  PaginatedResponse,
  ApiResponse,
  ApiError,
  MutationResult,
  // Data source types
  DataSource,
  OfflineDataSource,
  OfflineMetadata,
  WithOfflineMetadata,
  IdMapping,
} from './base';
export { DATA_SOURCE, OFFLINE_DATA_SOURCE } from './base';

// User types
export type {
  UserRole,
  UserStatus,
  UserPreferences,
  User,
  CreateUser,
  UpdateUser,
  UserFilters,
  UserWithRelations,
  UserProfile,
  UserPermissions,
} from './user';
export { getUserPermissions } from './user';

// Event types
export type {
  EventType,
  DeviceType,
  BrowserInfo,
  DeviceInfo,
  GeoLocation,
  PageContext,
  UtmParams,
  Event,
  CreateEvent,
  EventFilters,
  EventAggregation,
  EventWithComputed,
  EventBatch,
  EventCountByType,
  EventTimelineEntry,
  CommonEventProperty,
} from './event';
export { COMMON_EVENT_PROPERTIES } from './event';

// Session types
export type {
  SessionStatus,
  LandingPage,
  ExitPage,
  SessionMetrics,
  Session,
  CreateSession,
  UpdateSession,
  SessionFilters,
  SessionSummary,
  SessionWithEvents,
  SessionReplay,
  SessionFunnelStep,
  SessionCohort,
  ActiveSession,
  SessionTimeoutConfig,
} from './session';
export { DEFAULT_SESSION_TIMEOUT } from './session';

// JSON-serializable types
export type {
  JsonPrimitive,
  JsonObject,
  JsonArray,
  JsonValue,
  JsonSerializable,
} from './json-serializable';
export {
  isJsonSerializable,
  cloneJsonSerializable,
  toJsonSerializable,
  tryToJsonSerializable,
  assertJsonSerializable,
  JsonSerializationError,
} from './json-serializable';

// Result type for type-safe error handling (value export includes type)
export { Result } from './result';

// Branded types for type-safe primitives
// Brand is type-only; Milliseconds and Timestamp have both type and value exports
export type { Brand } from './branded';
// Value exports include their associated types automatically
export { Milliseconds, Timestamp, BrandedTypeValidationError } from './branded';

// ID branded types for sync-engine (value exports include type)
export { MutationId, EntityId, TabId, ProvisionalId } from './branded';

// Bridge branded types (centralized from foundation-bridge)
// Value exports include their types automatically
export { QueryId, WorkerId, SqlTableName, SqlIdentifier } from './branded';

// Query engine branded types (centralized from foundation-query-engine)
// Value exports include their types automatically
export { MemberRef, ExecutionId } from './branded';

// Sync-related types (type exports)
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
} from './sync';

// Sync-related constants (value exports)
export {
  CONFLICT_STRATEGY,
  CONFLICT_WINNER,
  SYNC_EVENT_TYPE,
  CROSS_TAB_MESSAGE_TYPE,
  OFFLINE_QUERY_SOURCE,
} from './sync';

// Realtime protocol types
export type {
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
} from './realtime';
export {
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
} from './realtime';

// Shared database contracts (used by foundation-database, sync-engine, bridge)
export type {
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
} from './database';
export {
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
} from './database';

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
} from './utility';

// Validation types
export type { ValidationSeverity, ValidationIssue, ValidationResultData } from './validation';
export { VALIDATION_SEVERITY, ValidationResult } from './validation';

// Type guards and safe conversions
export {
  // Arrow type guards
  isArrowVector,
  isArrowTable,
  isArrowField,
  // Generic type guards
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
  // Safe value conversions
  toNumber,
  toString,
  toBoolean,
  toDateIsoString,
  toDate,
  // Arrow value conversion
  ARROW_TYPE_ID,
  convertArrowValueSafe,
  convertArrowRow,
} from './type-guards';
