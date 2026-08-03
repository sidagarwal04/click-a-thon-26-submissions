/**
 * Metrics-Specific Constants
 *
 * All metrics constants use CAPITAL_SNAKE_CASE with derived PascalCase types.
 * Shared constants (Environment, ComplianceRegion, etc.) live in @foundation/data-model.
 *
 * @module types/constants
 */

import {
  SEVERITY_NUMBER,
  type SeverityNumberValue,
} from '@open-zentra/foundation-data-model';

export const ERROR_TYPE = {
  RUNTIME: 'runtime',
  UNHANDLED_REJECTION: 'unhandled_rejection',
  REACT_ERROR_BOUNDARY: 'react_error_boundary',
  NETWORK: 'network',
  RESOURCE: 'resource',
  CUSTOM: 'custom',
} as const;

export type ErrorType = (typeof ERROR_TYPE)[keyof typeof ERROR_TYPE];

export const WEB_VITAL_NAME = {
  LCP: 'LCP',
  CLS: 'CLS',
  INP: 'INP',
  FCP: 'FCP',
  TTFB: 'TTFB',
  FID: 'FID',
} as const;

export type WebVitalName = (typeof WEB_VITAL_NAME)[keyof typeof WEB_VITAL_NAME];

export const WEB_VITAL_RATING = {
  GOOD: 'good',
  NEEDS_IMPROVEMENT: 'needs-improvement',
  POOR: 'poor',
} as const;

export type WebVitalRating = (typeof WEB_VITAL_RATING)[keyof typeof WEB_VITAL_RATING];

export const INTERACTION_TYPE = {
  CLICK: 'click',
  INPUT: 'input',
  SCROLL: 'scroll',
  FOCUS: 'focus',
  BLUR: 'blur',
  SUBMIT: 'submit',
} as const;

export type InteractionType = (typeof INTERACTION_TYPE)[keyof typeof INTERACTION_TYPE];

export const SESSION_STATE = {
  ACTIVE: 'active',
  INACTIVE: 'inactive',
  EXPIRED: 'expired',
} as const;

export type SessionState = (typeof SESSION_STATE)[keyof typeof SESSION_STATE];

export const BREADCRUMB_CATEGORY = {
  NAVIGATION: 'navigation',
  UI: 'ui',
  NETWORK: 'network',
  CONSOLE: 'console',
  ERROR: 'error',
  CUSTOM: 'custom',
} as const;

export type BreadcrumbCategory = (typeof BREADCRUMB_CATEGORY)[keyof typeof BREADCRUMB_CATEGORY];

export const PII_FIELD_TYPE = {
  EMAIL: 'email',
  PHONE: 'phone',
  SSN: 'ssn',
  CREDIT_CARD: 'creditCard',
  ADDRESS: 'address',
  NAME: 'name',
  IP_ADDRESS: 'ipAddress',
  PASSWORD: 'password',
  API_KEY: 'apiKey',
  TOKEN: 'token',
  CUSTOM: 'custom',
} as const;

export type PiiFieldType = (typeof PII_FIELD_TYPE)[keyof typeof PII_FIELD_TYPE];

export const SAMPLING_DECISION = {
  SAMPLE: 'sample',
  DROP: 'drop',
} as const;

export type SamplingDecision = (typeof SAMPLING_DECISION)[keyof typeof SAMPLING_DECISION];

export const BUILT_IN_PLUGIN_NAME = {
  CONSOLE_LOGGER: 'console-logger',
  DEBUG_PANEL: 'debug-panel',
  PERFORMANCE_OBSERVER: 'performance-observer',
  SESSION_REPLAY: 'session-replay',
} as const;

export type BuiltInPluginName = (typeof BUILT_IN_PLUGIN_NAME)[keyof typeof BUILT_IN_PLUGIN_NAME];

export const SPAN_KIND = {
  INTERNAL: 'internal',
  CLIENT: 'client',
  SERVER: 'server',
  PRODUCER: 'producer',
  CONSUMER: 'consumer',
} as const;

export type SpanKindValue = (typeof SPAN_KIND)[keyof typeof SPAN_KIND];

export const SPA_NAVIGATION_TYPE = {
  PUSH: 'push',
  REPLACE: 'replace',
  POP: 'pop',
} as const;

export type SpaNavigationType = (typeof SPA_NAVIGATION_TYPE)[keyof typeof SPA_NAVIGATION_TYPE];

export const SAMPLER_SIGNAL_TYPE = {
  ERROR: 'error',
  TRACE: 'trace',
  METRIC: 'metric',
  USER_BEHAVIOR: 'userBehavior',
} as const;

export type SamplerSignalType = (typeof SAMPLER_SIGNAL_TYPE)[keyof typeof SAMPLER_SIGNAL_TYPE];

export const ENRICHER_SIGNAL_TYPE = {
  ERRORS: 'errors',
  PERFORMANCE: 'performance',
  NETWORK: 'network',
  USER_BEHAVIOR: 'userBehavior',
} as const;

export type EnricherSignalType = (typeof ENRICHER_SIGNAL_TYPE)[keyof typeof ENRICHER_SIGNAL_TYPE];

export const AUDIT_LOG_ACTION = {
  CONFIG_CHANGE: 'config_change',
  CONSENT_UPDATE: 'consent_update',
  DATA_EXPORT: 'data_export',
  DATA_DELETION: 'data_deletion',
  PII_ACCESS: 'pii_access',
} as const;

export type AuditLogAction = (typeof AUDIT_LOG_ACTION)[keyof typeof AUDIT_LOG_ACTION];

export const LOG_LEVEL = {
  TRACE: 'trace',
  DEBUG: 'debug',
  INFO: 'info',
  WARN: 'warn',
  ERROR: 'error',
  FATAL: 'fatal',
} as const;

export type MetricsLogLevel = (typeof LOG_LEVEL)[keyof typeof LOG_LEVEL];

export const LOG_LEVEL_TO_SEVERITY: Record<MetricsLogLevel, SeverityNumberValue> = {
  [LOG_LEVEL.TRACE]: SEVERITY_NUMBER.TRACE,
  [LOG_LEVEL.DEBUG]: SEVERITY_NUMBER.DEBUG,
  [LOG_LEVEL.INFO]: SEVERITY_NUMBER.INFO,
  [LOG_LEVEL.WARN]: SEVERITY_NUMBER.WARN,
  [LOG_LEVEL.ERROR]: SEVERITY_NUMBER.ERROR,
  [LOG_LEVEL.FATAL]: SEVERITY_NUMBER.FATAL,
};

export const NAVIGATION_TYPE = {
  NAVIGATE: 'navigate',
  RELOAD: 'reload',
  BACK_FORWARD: 'back-forward',
  BACK_FORWARD_CACHE: 'back-forward-cache',
  PRERENDER: 'prerender',
} as const;

export type NavigationType = (typeof NAVIGATION_TYPE)[keyof typeof NAVIGATION_TYPE];
