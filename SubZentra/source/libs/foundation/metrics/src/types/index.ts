/**
 * Foundation Metrics Type Definitions
 * @module types
 */

// Constants (metrics-specific)
export {
  ERROR_TYPE,
  type ErrorType,
  WEB_VITAL_NAME,
  type WebVitalName,
  WEB_VITAL_RATING,
  type WebVitalRating,
  INTERACTION_TYPE,
  type InteractionType,
  SESSION_STATE,
  type SessionState,
  BREADCRUMB_CATEGORY,
  type BreadcrumbCategory,
  PII_FIELD_TYPE,
  type PiiFieldType,
  SAMPLING_DECISION,
  type SamplingDecision,
  BUILT_IN_PLUGIN_NAME,
  type BuiltInPluginName,
  SPAN_KIND,
  type SpanKindValue,
  SPA_NAVIGATION_TYPE,
  type SpaNavigationType,
  SAMPLER_SIGNAL_TYPE,
  type SamplerSignalType,
  ENRICHER_SIGNAL_TYPE,
  type EnricherSignalType,
  AUDIT_LOG_ACTION,
  type AuditLogAction,
  LOG_LEVEL,
  type MetricsLogLevel,
  LOG_LEVEL_TO_SEVERITY,
  NAVIGATION_TYPE,
  type NavigationType,
} from './constants';

// Configuration types
export type {
  ErrorSignalConfig,
  PerformanceSignalConfig,
  NetworkSignalConfig,
  UserBehaviorSignalConfig,
  SamplingConfig,
  ComplianceConfig,
  TenantConfig,
  TransportConfig,
  SignalsConfig,
  FoundationMetricsConfig,
  ResolvedConfig,
} from './config';

// Signal types
export type {
  ErrorContext,
  CapturedError,
  WebVitalMetric,
  PageLoadTiming,
  SPANavigationEvent,
  LongTaskEntry,
  NetworkRequest,
  InteractionEvent,
  RageClickEvent,
  NavigationEvent,
  SessionData,
  SpanOptions,
  ActiveSpan,
  MessageContext,
  Breadcrumb,
  UserTraits,
} from './signals';

// Context types
export type {
  PageContext,
  AppContext,
  TenantContext,
  UserContext,
  SessionContext,
  TraceContext,
  ReleaseContext,
  TelemetryContext,
  ContextUpdate,
  EnricherFunction,
  EnricherConfig,
  ResourceAttributes,
  CommonSpanAttributes,
  HttpSpanAttributes,
  WebVitalSpanAttributes,
} from './context';

// Compliance types
export type {
  PIIDetectionResult,
  PIIPattern,
  FieldListConfig,
  DataRetentionConfig,
  RegionalCompliance,
  ConsentState,
  AuditLogEntry,
  SecurityContext,
  HashingConfig,
} from './compliance';

export {
  DEFAULT_URL_SANITIZATION,
  DEFAULT_DATA_RETENTION,
  REGIONAL_COMPLIANCE,
  DEFAULT_CONSENT_STATE,
  DEFAULT_HASHING_CONFIG,
} from './compliance';

// Plugin types
export type {
  PluginHooks,
  PluginMetadata,
  FoundationMetricsPlugin,
  PluginRegistrationOptions,
  PluginState,
  PluginManager,
  PluginFactory,
  AsyncPluginFactory,
} from './plugin';
