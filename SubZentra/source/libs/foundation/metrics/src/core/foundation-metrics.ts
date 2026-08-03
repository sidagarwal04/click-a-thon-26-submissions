/**
 * Foundation Metrics SDK
 * @module core/foundation-metrics
 */

import { SpanKind, SpanStatusCode, type Span } from '@opentelemetry/api';

import { isBrowser } from '@open-zentra/foundation-utils';

import type {
  ActiveSpan,
  Breadcrumb,
  ErrorContext,
  FoundationMetricsConfig,
  InteractionEvent,
  MessageContext,
  MetricsLogLevel,
  ResolvedConfig,
  SpanOptions,
  UserTraits,
  WebVitalMetric,
} from '../types';
import { BREADCRUMB_CATEGORY, ERROR_TYPE, LOG_LEVEL, SPAN_KIND } from '../types/constants';
import { resolveConfig, validateConfig } from './config-resolver';
import {
  clearUser as clearContextUser,
  getSpanAttributes,
  initializeContextManager,
  setTenant as setContextTenant,
  setUser as setContextUser,
  setCustomAttributes,
  shutdownContextManager,
} from './context-manager';
import {
  flushProviders,
  getMeter,
  getTracer,
  initializeOTelProviders,
  isInitialized as isOTelInitialized,
  shutdownProviders,
} from './otel-provider';

// =============================================================================
// Lifecycle State
// =============================================================================

/**
 * Lifecycle states for the metrics SDK.
 * Transitions: uninitialized → initializing → ready → shutting_down → shutdown
 * Re-initialization requires explicit reinitialize() call from shutdown state.
 */
type MetricsLifecycleState =
  | 'uninitialized'
  | 'initializing'
  | 'ready'
  | 'shutting_down'
  | 'shutdown';

// =============================================================================
// Module-level State
// =============================================================================

const breadcrumbs: Breadcrumb[] = [];
const MAX_BREADCRUMBS = 100;

/** Singleton instance */
let instance: FoundationMetrics | null = null;

/** Current lifecycle state */
let lifecycleState: MetricsLifecycleState = 'uninitialized';

/**
 * Foundation Metrics SDK
 *
 * Enterprise-grade frontend observability using OpenTelemetry.
 *
 * @example
 * ```typescript
 * import { FoundationMetrics } from '@open-zentra/foundation-metrics';
 *
 * FoundationMetrics.init({
 *   serviceName: 'my-app',
 *   collectorEndpoint: 'https://otel-collector.example.com',
 *   environment: 'production',
 *   version: '1.0.0',
 *   signals: {
 *     errors: true,
 *     performance: true,
 *     network: true,
 *     userBehavior: true,
 *   },
 *   sampling: {
 *     defaultRate: 1.0,
 *     errorRate: 1.0,
 *     traceRate: 0.1,
 *   },
 *   compliance: {
 *     piiFields: ['email', 'password'],
 *     region: 'us',
 *   },
 * });
 * ```
 */
export class FoundationMetrics {
  private config: ResolvedConfig;
  private isShutdown = false;

  // Store event handlers for cleanup on shutdown
  private pagehideHandler: (() => void) | null = null;
  private visibilityChangeHandler: (() => void) | null = null;

  /** Cached OTel instruments to avoid recreating per invocation */
  private readonly instrumentCache = new Map<
    string,
    | ReturnType<ReturnType<typeof getMeter>['createHistogram']>
    | ReturnType<ReturnType<typeof getMeter>['createCounter']>
  >();

  private constructor(config: ResolvedConfig) {
    this.config = config;
  }

  /**
   * Get or create a cached histogram instrument.
   */
  private getHistogram(name: string, options?: { description?: string; unit?: string }) {
    let instrument = this.instrumentCache.get(`h:${name}`);
    if (!instrument) {
      const meter = getMeter();
      instrument = meter.createHistogram(name, options);
      this.instrumentCache.set(`h:${name}`, instrument);
    }
    return instrument as ReturnType<ReturnType<typeof getMeter>['createHistogram']>;
  }

  /**
   * Get or create a cached counter instrument.
   */
  private getCounter(name: string, options?: { description?: string; unit?: string }) {
    let instrument = this.instrumentCache.get(`c:${name}`);
    if (!instrument) {
      const meter = getMeter();
      instrument = meter.createCounter(name, options);
      this.instrumentCache.set(`c:${name}`, instrument);
    }
    return instrument as ReturnType<ReturnType<typeof getMeter>['createCounter']>;
  }

  /**
   * Initialize the Foundation Metrics SDK.
   *
   * Uses a mutex to prevent race conditions during concurrent initialization.
   * If the SDK was previously shut down, call `reinitialize()` instead.
   */
  static init(config: FoundationMetricsConfig): FoundationMetrics {
    // Validate we're in a browser environment
    if (!isBrowser()) {
      console.warn('[FoundationMetrics] Not in browser environment, skipping initialization');
      return FoundationMetrics.createNoOpInstance(config);
    }

    // Return existing instance if already ready
    if (lifecycleState === 'ready' && instance && !instance.isShutdown) {
      console.warn('[FoundationMetrics] Already initialized, returning existing instance');
      return instance;
    }

    // Prevent re-init after shutdown — use reinitialize() instead
    if (lifecycleState === 'shutdown') {
      throw new Error(
        'FoundationMetrics was shut down. Call FoundationMetrics.reinitialize() to re-initialize, ' +
          'which properly cleans up previous OTel exporters before creating new ones.',
      );
    }

    // Prevent double init during initialization
    if (lifecycleState === 'initializing') {
      console.warn('[FoundationMetrics] Initialization already in progress');
      // Return a no-op instance as a safe fallback for the concurrent caller
      return FoundationMetrics.createNoOpInstance(config);
    }

    return FoundationMetrics.initializeInternal(config);
  }

  /**
   * Re-initialize the SDK after a shutdown.
   *
   * Unlike `init()`, this method is safe to call after `shutdown()` because it
   * properly transitions from the shutdown state to avoid duplicate OTel exporters.
   */
  static reinitialize(config: FoundationMetricsConfig): FoundationMetrics {
    if (!isBrowser()) {
      console.warn('[FoundationMetrics] Not in browser environment, skipping initialization');
      return FoundationMetrics.createNoOpInstance(config);
    }

    if (lifecycleState === 'ready' && instance && !instance.isShutdown) {
      console.warn('[FoundationMetrics] Already initialized, returning existing instance');
      return instance;
    }

    if (lifecycleState !== 'shutdown' && lifecycleState !== 'uninitialized') {
      throw new Error(
        `FoundationMetrics.reinitialize() can only be called in 'shutdown' or 'uninitialized' state ` +
          `(current: '${lifecycleState}')`,
      );
    }

    // Reset state to allow initialization
    lifecycleState = 'uninitialized';
    return FoundationMetrics.initializeInternal(config);
  }

  /**
   * Internal initialization logic shared by init() and reinitialize()
   */
  private static initializeInternal(config: FoundationMetricsConfig): FoundationMetrics {
    // Validate configuration
    const validationErrors = validateConfig(config);
    if (validationErrors.length > 0) {
      throw new Error(`FoundationMetrics configuration errors:\n${validationErrors.join('\n')}`);
    }

    lifecycleState = 'initializing';

    try {
      // Resolve configuration with defaults
      const resolvedConfig = resolveConfig(config);

      // Initialize OpenTelemetry providers
      initializeOTelProviders(resolvedConfig);

      // Initialize context manager
      initializeContextManager(resolvedConfig);

      // Create instance
      breadcrumbs.length = 0;
      instance = new FoundationMetrics(resolvedConfig);

      // Set up page unload handler
      instance.setupUnloadHandler();

      lifecycleState = 'ready';

      if (resolvedConfig.debug) {
        console.log('[FoundationMetrics] Initialized with config:', resolvedConfig);
      }

      return instance;
    } catch (error) {
      // Revert to uninitialized on failure so init() can be retried
      lifecycleState = 'uninitialized';
      instance = null;
      throw error;
    }
  }

  /**
   * Get the singleton instance
   */
  static getInstance(): FoundationMetrics {
    if (!instance) {
      throw new Error('FoundationMetrics not initialized. Call FoundationMetrics.init() first.');
    }
    return instance;
  }

  /**
   * Check if SDK is initialized and ready
   */
  static isInitialized(): boolean {
    return (
      lifecycleState === 'ready' && instance !== null && !instance.isShutdown && isOTelInitialized()
    );
  }

  /**
   * Get the current lifecycle state (for diagnostics)
   */
  static getLifecycleState(): MetricsLifecycleState {
    return lifecycleState;
  }

  /**
   * Create a no-op instance for SSR
   */
  private static createNoOpInstance(config: FoundationMetricsConfig): FoundationMetrics {
    const resolvedConfig = resolveConfig(config);
    const noOpInstance = new FoundationMetrics(resolvedConfig);
    noOpInstance.isShutdown = true; // Prevent operations
    return noOpInstance;
  }

  // ==========================================
  // Error Capture
  // ==========================================

  /**
   * Capture an error
   */
  captureError(error: Error, context?: ErrorContext): void {
    if (this.isShutdown || !this.config.signals.errors.enabled) {
      return;
    }

    const tracer = getTracer();
    const spanAttributes = getSpanAttributes();

    const span = tracer.startSpan('error', {
      kind: SpanKind.INTERNAL,
      attributes: {
        ...spanAttributes,
        'error.type': context?.type || ERROR_TYPE.CUSTOM,
        'error.message': error.message,
        'error.name': error.name,
        'error.stack': this.sanitizeStackTrace(error.stack),
        'component.name': context?.componentName,
        ...this.flattenMetadata(context?.metadata),
      },
    });

    span.setStatus({ code: SpanStatusCode.ERROR, message: error.message });
    span.end();

    // Add breadcrumb
    this.addBreadcrumb({
      category: 'error',
      message: error.message,
      timestamp: Date.now(),
      level: LOG_LEVEL.ERROR,
      data: { name: error.name, type: context?.type },
    });

    if (this.config.debug) {
      console.log('[FoundationMetrics] Captured error:', error.message);
    }
  }

  /**
   * Capture a message/log
   */
  captureMessage(
    message: string,
    level: MetricsLogLevel = LOG_LEVEL.INFO,
    context?: MessageContext,
  ): void {
    if (this.isShutdown) {
      return;
    }

    const tracer = getTracer();
    const spanAttributes = getSpanAttributes();

    const span = tracer.startSpan('log', {
      kind: SpanKind.INTERNAL,
      attributes: {
        ...spanAttributes,
        'log.level': level,
        'log.message': message,
        ...this.flattenMetadata(context?.attributes),
      },
    });

    if (level === LOG_LEVEL.ERROR || level === LOG_LEVEL.FATAL) {
      span.setStatus({ code: SpanStatusCode.ERROR, message });
    }

    span.end();

    // Add breadcrumb
    this.addBreadcrumb({
      category: BREADCRUMB_CATEGORY.CONSOLE,
      message,
      timestamp: Date.now(),
      level,
    });
  }

  // ==========================================
  // Performance
  // ==========================================

  /**
   * Start a new span for manual instrumentation
   */
  startSpan(name: string, options?: SpanOptions): ActiveSpan {
    if (this.isShutdown) {
      return this.createNoOpSpan();
    }

    const tracer = getTracer();
    const spanAttributes = getSpanAttributes();

    const spanKindMap = {
      [SPAN_KIND.INTERNAL]: SpanKind.INTERNAL,
      [SPAN_KIND.CLIENT]: SpanKind.CLIENT,
      [SPAN_KIND.SERVER]: SpanKind.SERVER,
      [SPAN_KIND.PRODUCER]: SpanKind.PRODUCER,
      [SPAN_KIND.CONSUMER]: SpanKind.CONSUMER,
    };

    const span = tracer.startSpan(name, {
      kind: options?.kind ? spanKindMap[options.kind] : SpanKind.INTERNAL,
      attributes: {
        ...spanAttributes,
        ...options?.attributes,
      },
      startTime: options?.startTime,
    });

    // Return wrapped span with helper methods
    return this.wrapSpan(span);
  }

  /**
   * Record a web vital metric
   */
  measureWebVital(metric: WebVitalMetric): void {
    if (this.isShutdown || !this.config.signals.performance.enabled) {
      return;
    }

    const histogram = this.getHistogram(`web_vital_${metric.name.toLowerCase()}`);
    const spanAttributes = getSpanAttributes();

    histogram.record(metric.value, {
      ...spanAttributes,
      'web_vital.name': metric.name,
      'web_vital.rating': metric.rating,
      'web_vital.navigation_type': metric.navigationType || 'unknown',
    });

    if (this.config.debug) {
      console.log(`[FoundationMetrics] Web Vital ${metric.name}:`, metric.value, metric.rating);
    }
  }

  // ==========================================
  // User Behavior
  // ==========================================

  /**
   * Track a user interaction
   */
  trackInteraction(event: InteractionEvent): void {
    if (this.isShutdown || !this.config.signals.userBehavior.enabled) {
      return;
    }

    // Apply sampling
    if (Math.random() > this.config.sampling.userBehaviorRate) {
      return;
    }

    const counter = this.getCounter('user_interactions');
    const spanAttributes = getSpanAttributes();

    counter.add(1, {
      ...spanAttributes,
      'interaction.type': event.type,
      'interaction.target_tag': event.targetTag,
      'interaction.target_id': event.targetId || '',
      'interaction.target_ozid': event.targetOzid || '',
    });

    // Add breadcrumb
    this.addBreadcrumb({
      category: BREADCRUMB_CATEGORY.UI,
      message: `${event.type} on ${event.targetTag}`,
      timestamp: event.timestamp,
      data: { targetId: event.targetId, targetOzid: event.targetOzid },
    });
  }

  /**
   * Track a navigation event
   */
  trackNavigation(route: string, previousRoute?: string): void {
    if (this.isShutdown || !this.config.signals.userBehavior.enabled) {
      return;
    }

    const tracer = getTracer();
    const spanAttributes = getSpanAttributes();

    const span = tracer.startSpan('navigation', {
      kind: SpanKind.INTERNAL,
      attributes: {
        ...spanAttributes,
        'navigation.from': previousRoute || '',
        'navigation.to': route,
      },
    });

    span.end();

    // Add breadcrumb
    this.addBreadcrumb({
      category: BREADCRUMB_CATEGORY.NAVIGATION,
      message: `Navigate to ${route}`,
      timestamp: Date.now(),
      data: { from: previousRoute, to: route },
    });
  }

  // ==========================================
  // Context Management
  // ==========================================

  /**
   * Set user context
   */
  setUser(userId: string, traits?: UserTraits): void {
    if (this.isShutdown) {
      return;
    }

    setContextUser(userId, traits);

    if (this.config.debug) {
      console.log('[FoundationMetrics] User set');
    }
  }

  /**
   * Clear user context (logout)
   */
  clearUser(): void {
    if (this.isShutdown) {
      return;
    }

    clearContextUser();
  }

  /**
   * Set tenant context
   */
  setTenant(tenantId: string, tier?: string): void {
    if (this.isShutdown) {
      return;
    }

    setContextTenant(tenantId, tier);

    if (this.config.debug) {
      console.log('[FoundationMetrics] Tenant set');
    }
  }

  /**
   * Set custom attributes
   */
  setAttributes(attributes: Record<string, string | number | boolean>): void {
    if (this.isShutdown) {
      return;
    }

    setCustomAttributes(attributes);
  }

  /**
   * Add a breadcrumb
   */
  addBreadcrumb(breadcrumb: Breadcrumb): void {
    if (this.isShutdown) {
      return;
    }

    breadcrumbs.push({
      ...breadcrumb,
      timestamp: breadcrumb.timestamp || Date.now(),
    });

    // Limit breadcrumbs
    while (breadcrumbs.length > MAX_BREADCRUMBS) {
      breadcrumbs.shift();
    }
  }

  /**
   * Get current breadcrumbs
   */
  getBreadcrumbs(): Breadcrumb[] {
    return [...breadcrumbs];
  }

  /**
   * Clear breadcrumbs
   */
  clearBreadcrumbs(): void {
    breadcrumbs.length = 0;
  }

  // ==========================================
  // Lifecycle
  // ==========================================

  /**
   * Flush all pending telemetry
   */
  async flush(): Promise<void> {
    if (this.isShutdown) {
      return;
    }

    await flushProviders();

    if (this.config.debug) {
      console.log('[FoundationMetrics] Flushed');
    }
  }

  /**
   * Shutdown the SDK.
   *
   * After shutdown, call `FoundationMetrics.reinitialize()` to start a new session.
   * Calling `init()` after shutdown will throw — this prevents accidental duplicate
   * OTel exporters from being registered.
   */
  async shutdown(): Promise<void> {
    if (this.isShutdown || lifecycleState === 'shutdown' || lifecycleState === 'shutting_down') {
      return;
    }

    lifecycleState = 'shutting_down';
    this.isShutdown = true;

    // Remove event listeners to prevent memory leaks
    this.removeUnloadHandlers();

    // Flush remaining data
    await this.flush();

    // Shutdown providers
    await shutdownProviders();

    // Shutdown context manager
    shutdownContextManager();

    // Clear in-memory state
    breadcrumbs.length = 0;
    this.instrumentCache.clear();
    instance = null;

    lifecycleState = 'shutdown';

    if (this.config.debug) {
      console.log('[FoundationMetrics] Shutdown complete');
    }
  }

  /**
   * Get current configuration
   */
  getConfig(): ResolvedConfig {
    return { ...this.config };
  }

  // ==========================================
  // Private Methods
  // ==========================================

  /**
   * Set up page unload handler
   */
  private setupUnloadHandler(): void {
    if (typeof window === 'undefined') {
      return;
    }

    // Store handlers for cleanup on shutdown
    this.pagehideHandler = () => {
      this.flush();
    };

    this.visibilityChangeHandler = () => {
      if (document.visibilityState === 'hidden') {
        this.flush();
      }
    };

    window.addEventListener('pagehide', this.pagehideHandler);
    document.addEventListener('visibilitychange', this.visibilityChangeHandler);
  }

  /**
   * Remove page unload handlers
   */
  private removeUnloadHandlers(): void {
    if (typeof window === 'undefined') {
      return;
    }

    if (this.pagehideHandler) {
      window.removeEventListener('pagehide', this.pagehideHandler);
      this.pagehideHandler = null;
    }

    if (this.visibilityChangeHandler) {
      document.removeEventListener('visibilitychange', this.visibilityChangeHandler);
      this.visibilityChangeHandler = null;
    }
  }

  /**
   * Sanitize stack trace
   */
  private sanitizeStackTrace(stack?: string): string {
    if (!stack) {
      return '';
    }
    return stack;
  }

  /**
   * Flatten metadata for span attributes
   */
  private flattenMetadata(
    metadata?: Record<string, unknown>,
  ): Record<string, string | number | boolean> {
    if (!metadata) {
      return {};
    }

    const result: Record<string, string | number | boolean> = {};

    for (const [key, value] of Object.entries(metadata)) {
      if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') {
        result[`metadata.${key}`] = value;
      } else if (value !== null && value !== undefined) {
        result[`metadata.${key}`] = JSON.stringify(value);
      }
    }

    return result;
  }

  /**
   * Wrap a span with helper methods
   */
  private wrapSpan(span: Span): ActiveSpan {
    const wrapped: ActiveSpan = {
      spanContext: () => span.spanContext(),
      setAttribute: (key, value) => {
        span.setAttribute(key, value);
        return wrapped;
      },
      setAttributes: (attrs) => {
        span.setAttributes(attrs);
        return wrapped;
      },
      addEvent: (name, attributes) => {
        span.addEvent(name, attributes);
        return wrapped;
      },
      setStatus: (status) => {
        span.setStatus(status);
        return wrapped;
      },
      updateName: (name) => {
        span.updateName(name);
        return wrapped;
      },
      isRecording: () => span.isRecording(),
      recordException: (exception) => span.recordException(exception),
      end: (endTime?: number) => span.end(endTime),
      setError: (error: Error) => {
        span.setStatus({ code: SpanStatusCode.ERROR, message: error.message });
        span.recordException(error);
      },
    };
    return wrapped;
  }

  /**
   * Create a no-op span for SSR
   */
  private createNoOpSpan(): ActiveSpan {
    const noOpSpan: ActiveSpan = {
      spanContext: () => ({ traceId: '', spanId: '', traceFlags: 0 }),
      setAttribute: () => noOpSpan,
      setAttributes: () => noOpSpan,
      addEvent: () => noOpSpan,
      setStatus: () => noOpSpan,
      updateName: () => noOpSpan,
      isRecording: () => false,
      recordException: () => undefined,
      end: () => undefined,
      setError: () => undefined,
    };
    return noOpSpan;
  }
}

/**
 * Reset all module-level state. Intended for test teardown only.
 * In production, use shutdown() + reinitialize() for proper cleanup.
 */
export const resetMetricsStateForTesting = (): void => {
  instance = null;
  breadcrumbs.length = 0;
  lifecycleState = 'uninitialized';
};

// Export convenience functions
export const init = FoundationMetrics.init.bind(FoundationMetrics);
export const reinitialize = FoundationMetrics.reinitialize.bind(FoundationMetrics);
export const getInstance = FoundationMetrics.getInstance.bind(FoundationMetrics);
export const isInitialized = FoundationMetrics.isInitialized.bind(FoundationMetrics);
export const getLifecycleState = FoundationMetrics.getLifecycleState.bind(FoundationMetrics);
