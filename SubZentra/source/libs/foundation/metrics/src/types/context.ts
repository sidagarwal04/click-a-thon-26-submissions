/**
 * Context and Enrichment Type Definitions
 * @module types/context
 */

import type { BrowserInfo } from '@open-zentra/foundation-utils';

import type { EnricherSignalType } from './constants';

/**
 * Page context
 */
export interface PageContext {
  url: string;
  route: string;
  title: string;
  referrer?: string;
  queryParams?: Record<string, string>;
}

/**
 * Application context
 */
export interface AppContext {
  serviceName: string;
  version: string;
  environment: string;
  deploymentId?: string;
  buildTimestamp?: string;
  commitHash?: string;
}

/**
 * Tenant context (hashed for privacy)
 */
export interface TenantContext {
  id: string;
  tier?: string;
  metadata?: Record<string, string>;
}

/**
 * User context (hashed/anonymized)
 */
export interface UserContext {
  id?: string;
  anonymousId: string;
  role?: string;
  isAuthenticated: boolean;
}

/**
 * Session context
 */
export interface SessionContext {
  id: string;
  startTime: number;
  isNew: boolean;
}

/**
 * Trace context for correlation
 */
export interface TraceContext {
  traceId: string;
  spanId: string;
  traceFlags: number;
  isSampled: boolean;
  parentSpanId?: string;
}

/**
 * Release context for deployment tracking
 */
export interface ReleaseContext {
  version: string;
  timestamp?: number;
  previousVersion?: string;
  environment: string;
}

/**
 * Full telemetry context
 */
export interface TelemetryContext {
  browser: BrowserInfo;
  page: PageContext;
  app: AppContext;
  tenant?: TenantContext;
  user: UserContext;
  session: SessionContext;
  trace?: TraceContext;
  release: ReleaseContext;
  custom?: Record<string, string | number | boolean>;
}

/**
 * Context update payload
 */
export interface ContextUpdate {
  user?: Partial<UserContext>;
  tenant?: Partial<TenantContext>;
  custom?: Record<string, string | number | boolean>;
}

/**
 * Enricher function type
 */
export type EnricherFunction = (context: TelemetryContext) => TelemetryContext;

/**
 * Enricher configuration
 */
export interface EnricherConfig {
  name: string;
  priority: number;
  enrich: EnricherFunction;
  signals?: EnricherSignalType[];
}

/**
 * Resource attributes for OpenTelemetry
 */
export interface ResourceAttributes {
  'service.name': string;
  'service.version': string;
  'service.namespace'?: string;
  'service.instance.id'?: string;
  'deployment.environment': string;
  'telemetry.sdk.name': string;
  'telemetry.sdk.version': string;
  'telemetry.sdk.language': string;
  'browser.name'?: string;
  'browser.version'?: string;
  'browser.platform'?: string;
  'browser.language'?: string;
  'user_agent.original'?: string;
  'device.type'?: string;
  'os.name'?: string;
  'os.version'?: string;
  [key: string]: string | number | boolean | undefined;
}

/**
 * Span attributes for common operations
 */
export interface CommonSpanAttributes {
  'component.name'?: string;
  'component.type'?: string;
  'operation.name'?: string;
  'page.route'?: string;
  'page.url'?: string;
  'user.id'?: string;
  'session.id'?: string;
  'tenant.id'?: string;
  error?: boolean;
  'error.type'?: string;
  'error.message'?: string;
}

/**
 * HTTP span attributes
 */
export interface HttpSpanAttributes extends CommonSpanAttributes {
  'http.method': string;
  'http.url': string;
  'http.route'?: string;
  'http.status_code'?: number;
  'http.request_content_length'?: number;
  'http.response_content_length'?: number;
  'http.retry_count'?: number;
}

/**
 * Web vital span attributes
 */
export interface WebVitalSpanAttributes extends CommonSpanAttributes {
  'web_vital.name': string;
  'web_vital.value': number;
  'web_vital.rating': string;
  'web_vital.navigation_type'?: string;
}
