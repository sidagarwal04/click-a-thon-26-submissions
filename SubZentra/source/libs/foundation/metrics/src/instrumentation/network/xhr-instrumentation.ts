/**
 * XMLHttpRequest Instrumentation
 * @module instrumentation/network/xhr-instrumentation
 */

import { context, propagation, SpanKind, SpanStatusCode, type Span } from '@opentelemetry/api';

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
 * XHR instrumentation state
 */
interface XHRInstrumentationState {
  config: NetworkSignalConfig;
  isInstalled: boolean;
  originalOpen: typeof XMLHttpRequest.prototype.open | null;
  originalSend: typeof XMLHttpRequest.prototype.send | null;
  callback?: (request: NetworkRequest) => void;
}

let state: XHRInstrumentationState | null = null;

/**
 * Metadata attached to XHR instances
 */
interface XHRMetadata {
  method: HttpMethod;
  url: string;
  startTime: number;
  span: Span;
}

const xhrMetadataMap = new WeakMap<XMLHttpRequest, XHRMetadata>();

/**
 * Handle XHR completion
 */
const handleXHRComplete = (xhr: XMLHttpRequest, metadata: XHRMetadata): void => {
  const duration = performance.now() - metadata.startTime;
  const statusCode = xhr.status;
  const success = statusCode >= 200 && statusCode < 400;

  metadata.span.setAttribute('http.status_code', statusCode);

  if (!success) {
    metadata.span.setStatus({
      code: SpanStatusCode.ERROR,
      message: `HTTP ${statusCode}`,
    });
  }

  metadata.span.end();

  const meter = getMeter();
  const spanAttributes = getSpanAttributes();

  const request: NetworkRequest = {
    url: sanitizeUrl(metadata.url),
    method: metadata.method,
    startTime: metadata.startTime,
    duration,
    statusCode,
    success,
    retryCount: 0,
    traceId: metadata.span.spanContext().traceId,
    spanId: metadata.span.spanContext().spanId,
  };

  recordNetworkMetrics(meter, request, spanAttributes, 'xhr');
  state?.callback?.(request);

  xhrMetadataMap.delete(xhr);
};

/**
 * Handle XHR error
 */
const handleXHRError = (xhr: XMLHttpRequest, metadata: XHRMetadata): void => {
  const duration = performance.now() - metadata.startTime;

  metadata.span.setStatus({
    code: SpanStatusCode.ERROR,
    message: 'Network error',
  });
  metadata.span.end();

  const meter = getMeter();
  const spanAttributes = getSpanAttributes();

  const request: NetworkRequest = {
    url: sanitizeUrl(metadata.url),
    method: metadata.method,
    startTime: metadata.startTime,
    duration,
    statusCode: 0,
    success: false,
    retryCount: 0,
    errorMessage: 'Network error',
    traceId: metadata.span.spanContext().traceId,
    spanId: metadata.span.spanContext().spanId,
  };

  recordNetworkMetrics(meter, request, spanAttributes, 'xhr');
  state?.callback?.(request);

  xhrMetadataMap.delete(xhr);
};

/**
 * Handle XHR abort
 */
const handleXHRAbort = (xhr: XMLHttpRequest, metadata: XHRMetadata): void => {
  const duration = performance.now() - metadata.startTime;

  metadata.span.setStatus({
    code: SpanStatusCode.ERROR,
    message: 'Request aborted',
  });
  metadata.span.end();

  const meter = getMeter();
  const spanAttributes = getSpanAttributes();

  const request: NetworkRequest = {
    url: sanitizeUrl(metadata.url),
    method: metadata.method,
    startTime: metadata.startTime,
    duration,
    statusCode: 0,
    success: false,
    retryCount: 0,
    errorMessage: 'Request aborted',
    traceId: metadata.span.spanContext().traceId,
    spanId: metadata.span.spanContext().spanId,
  };

  recordNetworkMetrics(meter, request, spanAttributes, 'xhr');
  state?.callback?.(request);

  xhrMetadataMap.delete(xhr);
};

/**
 * Handle XHR timeout
 */
const handleXHRTimeout = (xhr: XMLHttpRequest, metadata: XHRMetadata): void => {
  const duration = performance.now() - metadata.startTime;

  metadata.span.setStatus({
    code: SpanStatusCode.ERROR,
    message: 'Request timeout',
  });
  metadata.span.end();

  const meter = getMeter();
  const spanAttributes = getSpanAttributes();

  const request: NetworkRequest = {
    url: sanitizeUrl(metadata.url),
    method: metadata.method,
    startTime: metadata.startTime,
    duration,
    statusCode: 0,
    success: false,
    retryCount: 0,
    errorMessage: 'Request timeout',
    traceId: metadata.span.spanContext().traceId,
    spanId: metadata.span.spanContext().spanId,
  };

  recordNetworkMetrics(meter, request, spanAttributes, 'xhr');
  state?.callback?.(request);

  xhrMetadataMap.delete(xhr);
};

/**
 * Install XHR instrumentation
 */
export const installXHRInstrumentation = (
  config: NetworkSignalConfig,
  callback?: (request: NetworkRequest) => void,
): void => {
  if (typeof window === 'undefined' || typeof XMLHttpRequest === 'undefined') {
    return;
  }

  if (state?.isInstalled) {
    console.warn('[FoundationMetrics] XHR instrumentation already installed');
    return;
  }

  state = {
    config,
    isInstalled: false,
    originalOpen: XMLHttpRequest.prototype.open,
    originalSend: XMLHttpRequest.prototype.send,
    callback,
  };

  if (!config.trackXHR) {
    return;
  }

  // Patch open - regular function required for `this` binding
  XMLHttpRequest.prototype.open = function (
    method: string,
    url: string | URL,
    async = true,
    username?: string | null,
    password?: string | null,
  ) {
    const urlString = url.toString();

    // Check if URL should be ignored
    if (!shouldIgnoreUrl(urlString, state?.config.ignoreUrls ?? [])) {
      const tracer = getTracer();
      const spanAttributes = getSpanAttributes();

      const span = tracer.startSpan(`HTTP ${method.toUpperCase()}`, {
        kind: SpanKind.CLIENT,
        attributes: {
          ...spanAttributes,
          'http.method': method.toUpperCase(),
          'http.url': sanitizeUrl(urlString),
          'http.route': extractRoute(urlString),
        },
      });

      xhrMetadataMap.set(this, {
        method: toHttpMethod(method),
        url: urlString,
        startTime: performance.now(),
        span,
      });
    }

    return state!.originalOpen!.call(this, method, url, Boolean(async), username, password);
  };

  // Patch send - regular function required for `this` binding
  XMLHttpRequest.prototype.send = function (body?: Document | XMLHttpRequestBodyInit | null) {
    const metadata = xhrMetadataMap.get(this);

    if (metadata && state?.config.enabled) {
      // Inject trace context if allowed
      if (shouldPropagateTraceContext(metadata.url, state.config.propagateTraceContextTo)) {
        const carrier: Record<string, string> = {};
        propagation.inject(context.active(), carrier);
        Object.entries(carrier).forEach(([key, value]) => {
          try {
            this.setRequestHeader(key, value);
          } catch {
            // Header might already be set
          }
        });
      }

      // Add event listeners (arrow functions for handlers)
      this.addEventListener('load', () => handleXHRComplete(this, metadata));
      this.addEventListener('error', () => handleXHRError(this, metadata));
      this.addEventListener('abort', () => handleXHRAbort(this, metadata));
      this.addEventListener('timeout', () => handleXHRTimeout(this, metadata));
    }

    return state!.originalSend!.call(this, body);
  };

  state.isInstalled = true;
};

/**
 * Uninstall XHR instrumentation
 */
export const uninstallXHRInstrumentation = (): void => {
  if (state?.originalOpen && state?.originalSend) {
    XMLHttpRequest.prototype.open = state.originalOpen;
    XMLHttpRequest.prototype.send = state.originalSend;
  }
  state = null;
};

/**
 * Check if XHR instrumentation is installed
 */
export const isXHRInstrumentationInstalled = (): boolean => state?.isInstalled ?? false;
