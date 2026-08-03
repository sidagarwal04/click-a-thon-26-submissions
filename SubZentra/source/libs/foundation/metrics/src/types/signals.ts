/**
 * Signal Type Definitions
 * @module types/signals
 */

import type { SpanContext } from '@opentelemetry/api';

import type { HttpMethod } from '@open-zentra/foundation-data-model';

import type {
  BreadcrumbCategory,
  ErrorType,
  InteractionType,
  MetricsLogLevel,
  NavigationType,
  SessionState,
  SpaNavigationType,
  SpanKindValue,
  WebVitalName,
  WebVitalRating,
} from './constants';

// ==========================================
// Error Signals
// ==========================================

/**
 * Error context for capturing errors
 */
export interface ErrorContext {
  type?: ErrorType;
  componentName?: string;
  metadata?: Record<string, unknown>;
  tags?: string[];
  fingerprint?: string[];
  spanContext?: SpanContext;
}

/**
 * Captured error data
 */
export interface CapturedError {
  message: string;
  name: string;
  stack?: string;
  type: ErrorType;
  timestamp: number;
  filename?: string;
  lineno?: number;
  colno?: number;
  context: ErrorContext;
}

// ==========================================
// Performance Signals
// ==========================================

/**
 * Web Vital metric
 */
export interface WebVitalMetric {
  name: WebVitalName;
  value: number;
  rating: WebVitalRating;
  delta: number;
  id: string;
  navigationType?: NavigationType;
  attribution?: Record<string, unknown>;
}

/**
 * Page load timing data
 */
export interface PageLoadTiming {
  dnsLookup: number;
  tcpConnection: number;
  tlsNegotiation: number;
  ttfb: number;
  contentDownload: number;
  domInteractive: number;
  domContentLoaded: number;
  loadComplete: number;
}

/**
 * SPA navigation event
 */
export interface SPANavigationEvent {
  type: SpaNavigationType;
  from: string;
  to: string;
  duration: number;
  timestamp: number;
}

/**
 * Long task entry
 */
export interface LongTaskEntry {
  duration: number;
  startTime: number;
  name: string;
  attribution: {
    containerType?: string;
    containerSrc?: string;
    containerId?: string;
    containerName?: string;
  }[];
}

// ==========================================
// Network Signals
// ==========================================

/**
 * Network request data
 */
export interface NetworkRequest {
  url: string;
  method: HttpMethod;
  startTime: number;
  duration: number;
  statusCode: number;
  responseSize?: number;
  requestSize?: number;
  success: boolean;
  retryCount: number;
  errorMessage?: string;
  traceId?: string;
  spanId?: string;
}

// ==========================================
// User Behavior Signals
// ==========================================

/**
 * Interaction event
 */
export interface InteractionEvent {
  type: InteractionType;
  targetTag: string;
  targetId?: string;
  targetClasses?: string[];
  targetOzid?: string;
  timestamp: number;
  route: string;
  metadata?: Record<string, unknown>;
}

/**
 * Rage click event
 */
export interface RageClickEvent {
  clickCount: number;
  targetSelector: string;
  targetOzid?: string;
  windowDuration: number;
  firstClickTime: number;
  lastClickTime: number;
  route: string;
}

/**
 * Navigation event
 */
export interface NavigationEvent {
  from?: string;
  to: string;
  timestamp: number;
  timeOnPreviousPage?: number;
}

/**
 * Session data
 */
export interface SessionData {
  id: string;
  startTime: number;
  lastActivityTime: number;
  state: SessionState;
  pageViewCount: number;
  interactionCount: number;
  errorCount: number;
}

// ==========================================
// Span Types
// ==========================================

/**
 * Span options for manual instrumentation
 */
export interface SpanOptions {
  kind?: SpanKindValue;
  attributes?: Record<string, string | number | boolean>;
  parentContext?: SpanContext;
  startTime?: number;
}

/**
 * Active span wrapper - simplified interface for SDK users
 */
export interface ActiveSpan {
  spanContext(): { traceId: string; spanId: string; traceFlags: number };
  setAttribute(key: string, value: string | number | boolean): ActiveSpan;
  setAttributes(attributes: Record<string, string | number | boolean>): ActiveSpan;
  addEvent(name: string, attributes?: Record<string, string | number | boolean>): ActiveSpan;
  setStatus(status: { code: number; message?: string }): ActiveSpan;
  updateName(name: string): ActiveSpan;
  isRecording(): boolean;
  recordException(exception: Error): void;
  end(endTime?: number): void;
  setError(error: Error): void;
}

// ==========================================
// Message/Log Signals
// ==========================================

/**
 * Message context for custom logging
 */
export interface MessageContext {
  level?: MetricsLogLevel;
  attributes?: Record<string, unknown>;
  tags?: string[];
  spanContext?: SpanContext;
}

// ==========================================
// Breadcrumbs
// ==========================================

/**
 * Breadcrumb entry
 */
export interface Breadcrumb {
  category: BreadcrumbCategory;
  message: string;
  timestamp: number;
  level?: MetricsLogLevel;
  data?: Record<string, unknown>;
}

// ==========================================
// User Context
// ==========================================

/**
 * User traits for identification
 */
export interface UserTraits {
  email?: string;
  name?: string;
  role?: string;
  [key: string]: unknown;
}
