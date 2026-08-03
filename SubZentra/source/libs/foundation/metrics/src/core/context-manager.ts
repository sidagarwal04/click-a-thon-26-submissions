/**
 * Context Manager for Telemetry
 * @module core/context-manager
 */

import { context, propagation, trace, type SpanContext } from '@opentelemetry/api';

import {
  detectBrowser,
  generateId,
  getCurrentPageUrl,
  getCurrentRoute,
  hashStringSync,
  type BrowserInfo,
} from '@open-zentra/foundation-utils';

import type {
  AppContext,
  ContextUpdate,
  PageContext,
  ReleaseContext,
  ResolvedConfig,
  SessionContext,
  TelemetryContext,
  TenantContext,
  TraceContext,
  UserContext,
} from '../types';

/**
 * Context manager state
 */
interface ContextManagerState {
  browser: BrowserInfo;
  page: PageContext;
  app: AppContext;
  tenant?: TenantContext;
  user: UserContext;
  session: SessionContext;
  release: ReleaseContext;
  custom: Record<string, string | number | boolean>;
  config: ResolvedConfig;
}

let contextState: ContextManagerState | null = null;

/**
 * Initialize the context manager
 */
export function initializeContextManager(config: ResolvedConfig): void {
  const browser = detectBrowser();
  const sessionId = generateSessionId();
  const anonymousId = getOrCreateAnonymousId();

  contextState = {
    browser,
    page: getCurrentPageContext(),
    app: {
      serviceName: config.serviceName,
      version: config.version,
      environment: config.environment,
    },
    tenant: config.tenant
      ? {
          id: hashTenantId(config.tenant.id, config.compliance.tenantHashSalt),
          tier: config.tenant.tier,
          metadata: config.tenant.metadata,
        }
      : undefined,
    user: {
      anonymousId,
      isAuthenticated: false,
    },
    session: {
      id: sessionId,
      startTime: Date.now(),
      isNew: true,
    },
    release: {
      version: config.version,
      environment: config.environment,
    },
    custom: {},
    config,
  };

  // Set up page visibility change listener
  if (typeof document !== 'undefined') {
    document.addEventListener('visibilitychange', handleVisibilityChange);
  }

  // Set up navigation listener for SPA
  if (typeof window !== 'undefined') {
    window.addEventListener('popstate', handleNavigation);
  }
}

/**
 * Get the current telemetry context
 */
export function getTelemetryContext(): TelemetryContext {
  if (!contextState) {
    throw new Error('Context manager not initialized');
  }

  return {
    browser: contextState.browser,
    page: getCurrentPageContext(),
    app: contextState.app,
    tenant: contextState.tenant,
    user: contextState.user,
    session: contextState.session,
    trace: getCurrentTraceContext(),
    release: contextState.release,
    custom: contextState.custom,
  };
}

/**
 * Update user context
 */
export function setUser(userId: string, traits?: Record<string, unknown>): void {
  if (!contextState) {
    throw new Error('Context manager not initialized');
  }

  const salt = contextState.config.compliance.tenantHashSalt || '';

  const role = typeof traits?.role === 'string' ? traits.role : undefined;

  contextState.user = {
    ...contextState.user,
    id: hashStringSync(userId, salt),
    isAuthenticated: true,
    role,
  };
}

/**
 * Clear user context (on logout)
 */
export function clearUser(): void {
  if (!contextState) {
    return;
  }

  contextState.user = {
    anonymousId: contextState.user.anonymousId,
    isAuthenticated: false,
  };
}

/**
 * Update tenant context
 */
export function setTenant(
  tenantId: string,
  tier?: string,
  metadata?: Record<string, string>,
): void {
  if (!contextState) {
    throw new Error('Context manager not initialized');
  }

  const salt = contextState.config.compliance.tenantHashSalt || '';

  contextState.tenant = {
    id: hashTenantId(tenantId, salt),
    tier,
    metadata,
  };
}

/**
 * Update custom context attributes
 */
export function setCustomAttributes(attributes: Record<string, string | number | boolean>): void {
  if (!contextState) {
    return;
  }

  contextState.custom = {
    ...contextState.custom,
    ...attributes,
  };
}

/**
 * Update context with partial updates
 */
export function updateContext(update: ContextUpdate): void {
  if (!contextState) {
    return;
  }

  if (update.user) {
    contextState.user = {
      ...contextState.user,
      ...update.user,
    };
  }

  if (update.tenant && contextState.tenant) {
    // Ensure id is always present from existing tenant
    contextState.tenant = {
      id: contextState.tenant.id,
      tier: update.tenant.tier ?? contextState.tenant.tier,
      metadata: update.tenant.metadata ?? contextState.tenant.metadata,
    };
  }

  if (update.custom) {
    contextState.custom = {
      ...contextState.custom,
      ...update.custom,
    };
  }
}

/**
 * Update session activity
 */
export function updateSessionActivity(): void {
  if (!contextState) {
    return;
  }

  contextState.session = {
    ...contextState.session,
    isNew: false,
  };
}

/**
 * Start a new session
 */
export function startNewSession(): void {
  if (!contextState) {
    return;
  }

  contextState.session = {
    id: generateSessionId(),
    startTime: Date.now(),
    isNew: true,
  };
}

/**
 * Get the current page context
 */
function getCurrentPageContext(): PageContext {
  if (typeof window === 'undefined') {
    return {
      url: '',
      route: '',
      title: '',
    };
  }

  return {
    url: getCurrentPageUrl({ removeQueryParams: false, removeHash: true }),
    route: getCurrentRoute(),
    title: document.title || '',
    referrer: document.referrer || undefined,
  };
}

/**
 * Get current trace context from OpenTelemetry
 */
function getCurrentTraceContext(): TraceContext | undefined {
  const span = trace.getActiveSpan();
  if (!span) {
    return undefined;
  }

  const spanContext: SpanContext = span.spanContext();

  return {
    traceId: spanContext.traceId,
    spanId: spanContext.spanId,
    traceFlags: spanContext.traceFlags,
    isSampled: (spanContext.traceFlags & 1) === 1,
  };
}

/**
 * Hash tenant ID for privacy
 */
function hashTenantId(tenantId: string, salt?: string): string {
  return hashStringSync(tenantId, salt || '');
}

/**
 * Generate a new session ID
 */
function generateSessionId(): string {
  const id = generateId();

  // Store in session storage for persistence
  if (typeof sessionStorage !== 'undefined') {
    try {
      sessionStorage.setItem('fm_session_id', id);
    } catch {
      // Session storage not available
    }
  }

  return id;
}

/**
 * Get or create anonymous ID
 */
function getOrCreateAnonymousId(): string {
  const storageKey = 'fm_anonymous_id';

  // Try to get from localStorage
  if (typeof localStorage !== 'undefined') {
    try {
      const existingId = localStorage.getItem(storageKey);
      if (existingId) {
        return existingId;
      }

      const newId = generateId();
      localStorage.setItem(storageKey, newId);
      return newId;
    } catch {
      // localStorage not available
    }
  }

  // Fallback to generating a new ID
  return generateId();
}

/**
 * Handle page visibility change
 */
function handleVisibilityChange(): void {
  if (!contextState) {
    return;
  }

  if (document.visibilityState === 'visible') {
    updateSessionActivity();
  }
}

/**
 * Handle navigation events
 */
function handleNavigation(): void {
  if (!contextState) {
    return;
  }

  contextState.page = getCurrentPageContext();
}

/**
 * Get context attributes for spans
 */
export function getSpanAttributes(): Record<string, string | number | boolean | undefined> {
  const ctx = getTelemetryContext();

  return {
    'page.route': ctx.page.route,
    'page.url': ctx.page.url,
    'session.id': ctx.session.id,
    'user.id': ctx.user.id,
    'user.anonymous_id': ctx.user.anonymousId,
    'user.authenticated': ctx.user.isAuthenticated,
    'tenant.id': ctx.tenant?.id,
    'tenant.tier': ctx.tenant?.tier,
    'app.version': ctx.app.version,
    'app.environment': ctx.app.environment,
    ...ctx.custom,
  };
}

/**
 * Inject trace context into headers for outgoing requests
 */
export function injectTraceContext(headers: Headers): Headers {
  const carrier: Record<string, string> = {};
  propagation.inject(context.active(), carrier);

  Object.entries(carrier).forEach(([key, value]) => {
    headers.set(key, value);
  });

  return headers;
}

/**
 * Extract trace context from headers for incoming requests
 */
export function extractTraceContext(headers: Headers): SpanContext | undefined {
  const carrier: Record<string, string> = {};
  headers.forEach((value, key) => {
    carrier[key] = value;
  });

  const extractedContext = propagation.extract(context.active(), carrier);
  const span = trace.getSpan(extractedContext);

  return span?.spanContext();
}

/**
 * Shutdown context manager
 */
export function shutdownContextManager(): void {
  if (typeof document !== 'undefined') {
    document.removeEventListener('visibilitychange', handleVisibilityChange);
  }

  if (typeof window !== 'undefined') {
    window.removeEventListener('popstate', handleNavigation);
  }

  contextState = null;
}
