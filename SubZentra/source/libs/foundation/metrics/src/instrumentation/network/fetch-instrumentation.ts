/**
 * Fetch API Instrumentation
 * @module instrumentation/network/fetch-instrumentation
 */

import { context, propagation, SpanKind, SpanStatusCode } from '@opentelemetry/api';

import type { HttpMethod } from '@open-zentra/foundation-data-model';
import {
  extractRoute,
  sanitizeUrl,
  shouldIgnoreUrl,
  shouldPropagateTraceContext,
} from '@open-zentra/foundation-utils';

import { getSpanAttributes } from '../../core/context-manager';
import { getMeter, getTracer } from '../../core/otel-provider';
import type { NetworkRequest, NetworkSignalConfig } from '../../types';
import { recordNetworkMetrics, toHttpMethod } from '../../utils/http-utils';

/**
 * Fetch instrumentation state
 */
interface FetchInstrumentationState {
  config: NetworkSignalConfig;
  isInstalled: boolean;
  originalFetch: typeof fetch | null;
  callback?: (request: NetworkRequest) => void;
}

let state: FetchInstrumentationState | null = null;

/**
 * Get URL string from fetch input
 */
const getUrlFromInput = (input: RequestInfo | URL): string => {
  if (typeof input === 'string') {
    return input;
  }
  if (input instanceof URL) {
    return input.toString();
  }
  if (input instanceof Request) {
    return input.url;
  }
  return String(input);
};

/**
 * Instrumented fetch function
 */
const instrumentedFetch = async (
  input: RequestInfo | URL,
  init?: RequestInit,
): Promise<Response> => {
  if (!state?.config.enabled || !state.originalFetch) {
    return state?.originalFetch?.(input, init) ?? fetch(input, init);
  }

  const url = getUrlFromInput(input);

  // Check if URL should be ignored
  if (shouldIgnoreUrl(url, state.config.ignoreUrls)) {
    return state.originalFetch(input, init);
  }

  const method: HttpMethod = toHttpMethod(init?.method || 'GET');
  const tracer = getTracer();
  const meter = getMeter();
  const spanAttributes = getSpanAttributes();
  const startTime = performance.now();

  // Create span
  const span = tracer.startSpan(`HTTP ${method}`, {
    kind: SpanKind.CLIENT,
    attributes: {
      ...spanAttributes,
      'http.method': method,
      'http.url': sanitizeUrl(url),
      'http.route': extractRoute(url),
    },
  });

  // Inject trace context if allowed
  const headers = new Headers(init?.headers);
  if (shouldPropagateTraceContext(url, state.config.propagateTraceContextTo)) {
    const carrier: Record<string, string> = {};
    propagation.inject(context.active(), carrier);
    Object.entries(carrier).forEach(([key, value]) => {
      headers.set(key, value);
    });
  }

  try {
    const response = await state.originalFetch(input, { ...init, headers });
    const duration = performance.now() - startTime;

    // Update span
    span.setAttribute('http.status_code', response.status);

    if (!response.ok) {
      span.setStatus({
        code: SpanStatusCode.ERROR,
        message: `HTTP ${response.status}`,
      });
    }

    span.end();

    // Record metrics
    recordNetworkMetrics(
      meter,
      {
        url: sanitizeUrl(url),
        method,
        startTime,
        duration,
        statusCode: response.status,
        success: response.ok,
        retryCount: 0,
        traceId: span.spanContext().traceId,
        spanId: span.spanContext().spanId,
      },
      spanAttributes,
    );

    // Call callback
    state.callback?.({
      url: sanitizeUrl(url),
      method,
      startTime,
      duration,
      statusCode: response.status,
      success: response.ok,
      retryCount: 0,
      traceId: span.spanContext().traceId,
      spanId: span.spanContext().spanId,
    });

    return response;
  } catch (error) {
    const duration = performance.now() - startTime;

    span.setStatus({
      code: SpanStatusCode.ERROR,
      message: error instanceof Error ? error.message : 'Unknown error',
    });
    if (error instanceof Error) {
      span.recordException(error);
    }
    span.end();

    // Record error metrics
    recordNetworkMetrics(
      meter,
      {
        url: sanitizeUrl(url),
        method,
        startTime,
        duration,
        statusCode: 0,
        success: false,
        retryCount: 0,
        errorMessage: error instanceof Error ? error.message : 'Unknown error',
        traceId: span.spanContext().traceId,
        spanId: span.spanContext().spanId,
      },
      spanAttributes,
    );

    // Call callback
    state.callback?.({
      url: sanitizeUrl(url),
      method,
      startTime,
      duration,
      statusCode: 0,
      success: false,
      retryCount: 0,
      errorMessage: error instanceof Error ? error.message : 'Unknown error',
      traceId: span.spanContext().traceId,
      spanId: span.spanContext().spanId,
    });

    throw error;
  }
};

/**
 * Install fetch instrumentation
 */
export const installFetchInstrumentation = (
  config: NetworkSignalConfig,
  callback?: (request: NetworkRequest) => void,
): void => {
  if (typeof window === 'undefined' || typeof fetch === 'undefined') {
    return;
  }

  if (state?.isInstalled) {
    console.warn('[FoundationMetrics] Fetch instrumentation already installed');
    return;
  }

  state = {
    config,
    isInstalled: false,
    originalFetch: window.fetch.bind(window),
    callback,
  };

  if (!config.trackFetch) {
    return;
  }

  // Patch fetch
  window.fetch = instrumentedFetch;

  state.isInstalled = true;
};

/**
 * Uninstall fetch instrumentation
 */
export const uninstallFetchInstrumentation = (): void => {
  if (state?.originalFetch && typeof window !== 'undefined') {
    window.fetch = state.originalFetch;
  }
  state = null;
};

/**
 * Check if fetch instrumentation is installed
 */
export const isFetchInstrumentationInstalled = (): boolean => state?.isInstalled ?? false;
