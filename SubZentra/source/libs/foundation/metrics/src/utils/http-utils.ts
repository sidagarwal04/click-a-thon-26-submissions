/**
 * HTTP utilities for network instrumentation
 *
 * Shared utilities for fetch and XHR instrumentation to avoid code duplication.
 *
 * @module utils/http-utils
 */

import type { Attributes } from '@opentelemetry/api';

import { HTTP_METHOD, type HttpMethod } from '@open-zentra/foundation-data-model';
import { extractRoute } from '@open-zentra/foundation-utils';

import type { NetworkRequest } from '../types';

/**
 * Set of valid HTTP methods for validation
 */
const VALID_HTTP_METHODS: Set<string> = new Set(Object.values(HTTP_METHOD));
const HTTP_METHOD_BY_VALUE: Record<string, HttpMethod> = {
  [HTTP_METHOD.GET]: HTTP_METHOD.GET,
  [HTTP_METHOD.POST]: HTTP_METHOD.POST,
  [HTTP_METHOD.PUT]: HTTP_METHOD.PUT,
  [HTTP_METHOD.DELETE]: HTTP_METHOD.DELETE,
  [HTTP_METHOD.PATCH]: HTTP_METHOD.PATCH,
  [HTTP_METHOD.HEAD]: HTTP_METHOD.HEAD,
  [HTTP_METHOD.OPTIONS]: HTTP_METHOD.OPTIONS,
};

/**
 * Check if a value is a valid HTTP method
 */
export const isValidHttpMethod = (method: unknown): method is HttpMethod =>
  typeof method === 'string' && VALID_HTTP_METHODS.has(method.toUpperCase());

/**
 * Convert a value to a valid HTTP method, defaulting to GET
 */
export const toHttpMethod = (method: unknown): HttpMethod => {
  if (typeof method !== 'string') return HTTP_METHOD.GET;
  const upper = method.toUpperCase();
  return HTTP_METHOD_BY_VALUE[upper] ?? HTTP_METHOD.GET;
};

/**
 * Meter-like interface for recording metrics (avoids coupling to OTel types)
 */
interface MetricsRecorder {
  createHistogram: (
    name: string,
    opts?: { description?: string; unit?: string },
  ) => {
    record: (value: number, attrs?: Attributes) => void;
  };
  createCounter: (
    name: string,
    opts?: { description?: string },
  ) => {
    add: (value: number, attrs?: Attributes) => void;
  };
}

/**
 * Record network metrics to OpenTelemetry meter.
 * Shared by both fetch and XHR instrumentation.
 */
export const recordNetworkMetrics = (
  meter: MetricsRecorder,
  request: NetworkRequest,
  spanAttributes: Record<string, string | number | boolean | undefined>,
  client?: string,
): void => {
  const route = extractRoute(request.url);

  const baseAttrs = {
    ...spanAttributes,
    'http.method': request.method,
    'http.route': route,
    'http.status_code': request.statusCode,
    ...(client ? { 'http.client': client } : {}),
  };

  const latencyHistogram = meter.createHistogram('http_client_duration_ms', {
    description: 'HTTP client request duration in milliseconds',
    unit: 'ms',
  });
  latencyHistogram.record(request.duration, baseAttrs);

  const requestCounter = meter.createCounter('http_client_requests_total', {
    description: 'Total number of HTTP client requests',
  });
  requestCounter.add(1, baseAttrs);

  if (!request.success) {
    const errorCounter = meter.createCounter('http_client_errors_total', {
      description: 'Total number of HTTP client errors',
    });
    errorCounter.add(1, baseAttrs);
  }
};
