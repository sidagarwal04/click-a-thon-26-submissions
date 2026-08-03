/**
 * Error Instrumentation
 * @module instrumentation/errors/error-instrumentation
 */

import { SpanKind, SpanStatusCode } from '@opentelemetry/api';

import { getSpanAttributes } from '../../core/context-manager';
import { getTracer } from '../../core/otel-provider';
import type { CapturedError, ErrorContext, ErrorSignalConfig } from '../../types';

/**
 * Error instrumentation state
 */
interface ErrorInstrumentationState {
  config: ErrorSignalConfig;
  isInstalled: boolean;
  originalOnError: OnErrorEventHandler | null;
  originalOnUnhandledRejection: ((event: PromiseRejectionEvent) => void) | null;
  errorCallback?: (error: CapturedError) => void;
  // Bound event listeners for proper cleanup
  boundUnhandledRejectionHandler: (event: Event) => void;
  boundErrorEventHandler: (event: Event) => void;
}

let state: ErrorInstrumentationState | null = null;

/**
 * Wrapper for unhandled rejection handler that accepts Event type
 */
function createUnhandledRejectionWrapper(
  handler: (event: PromiseRejectionEvent) => void,
): (event: Event) => void {
  return (event: Event) => {
    if (event instanceof PromiseRejectionEvent) {
      handler(event);
    }
  };
}

/**
 * Wrapper for error event handler that accepts Event type
 */
function createErrorEventWrapper(handler: (event: ErrorEvent) => void): (event: Event) => void {
  return (event: Event) => {
    if (event instanceof ErrorEvent) {
      handler(event);
    }
  };
}

/**
 * Install error instrumentation
 */
export function installErrorInstrumentation(
  config: ErrorSignalConfig,
  callback?: (error: CapturedError) => void,
): void {
  if (typeof window === 'undefined') {
    return;
  }

  if (state?.isInstalled) {
    console.warn('[FoundationMetrics] Error instrumentation already installed');
    return;
  }

  state = {
    config,
    isInstalled: false,
    originalOnError: null,
    originalOnUnhandledRejection: null,
    errorCallback: callback,
    boundUnhandledRejectionHandler: createUnhandledRejectionWrapper(handleUnhandledRejection),
    boundErrorEventHandler: createErrorEventWrapper(handleErrorEvent),
  };

  if (config.captureGlobalErrors) {
    installGlobalErrorHandler();
  }

  if (config.captureUnhandledRejections) {
    installUnhandledRejectionHandler();
  }

  state.isInstalled = true;
}

/**
 * Uninstall error instrumentation
 */
export function uninstallErrorInstrumentation(): void {
  if (!state?.isInstalled || typeof window === 'undefined') {
    return;
  }

  // Restore original handlers
  if (state.originalOnError !== null) {
    window.onerror = state.originalOnError;
  }

  // Remove event listeners using bound handlers
  window.removeEventListener('unhandledrejection', state.boundUnhandledRejectionHandler);
  window.removeEventListener('error', state.boundErrorEventHandler, true);

  state = null;
}

/**
 * Install global error handler
 */
function installGlobalErrorHandler(): void {
  if (!state || typeof window === 'undefined') {
    return;
  }

  // Store original handler
  state.originalOnError = window.onerror;

  // Install new handler
  window.onerror = (
    message: string | Event,
    filename?: string,
    lineno?: number,
    colno?: number,
    error?: Error,
  ) => {
    handleGlobalError(message, filename, lineno, colno, error);

    // Call original handler if exists
    if (state?.originalOnError) {
      return state.originalOnError(message, filename, lineno, colno, error);
    }

    return false;
  };

  // Also listen for error events on window using bound handler
  window.addEventListener('error', state.boundErrorEventHandler, true);
}

/**
 * Install unhandled rejection handler
 */
function installUnhandledRejectionHandler(): void {
  if (!state || typeof window === 'undefined') {
    return;
  }

  window.addEventListener('unhandledrejection', state.boundUnhandledRejectionHandler);
}

/**
 * Handle global errors
 */
function handleGlobalError(
  message: string | Event,
  filename?: string,
  lineno?: number,
  colno?: number,
  error?: Error,
): void {
  if (!state?.config.enabled) {
    return;
  }

  const errorMessage = typeof message === 'string' ? message : message.type;
  const capturedError: CapturedError = {
    message: errorMessage,
    name: error?.name || 'Error',
    stack: sanitizeStack(error?.stack),
    type: 'runtime',
    timestamp: Date.now(),
    filename,
    lineno,
    colno,
    context: {},
  };

  recordError(capturedError);
  state.errorCallback?.(capturedError);
}

/**
 * Handle error events (for resource loading errors, etc.)
 */
function handleErrorEvent(event: ErrorEvent): void {
  if (!state?.config.enabled) {
    return;
  }

  // Skip if this is a script error (handled by onerror)
  if (event.error) {
    return;
  }

  // This catches resource loading errors
  const target = event.target;
  if (target && target instanceof HTMLElement) {
    const capturedError: CapturedError = {
      message: `Failed to load resource: ${getResourceUrl(target)}`,
      name: 'ResourceError',
      type: 'resource',
      timestamp: Date.now(),
      context: {
        metadata: {
          tagName: target.tagName,
          src: getResourceUrl(target),
        },
      },
    };

    recordError(capturedError);
    state.errorCallback?.(capturedError);
  }
}

/**
 * Handle unhandled promise rejections
 */
function handleUnhandledRejection(event: PromiseRejectionEvent): void {
  if (!state?.config.enabled) {
    return;
  }

  const reason = event.reason;
  let message: string;
  let stack: string | undefined;
  let name: string;

  if (reason instanceof Error) {
    message = reason.message;
    stack = reason.stack;
    name = reason.name;
  } else if (typeof reason === 'string') {
    message = reason;
    name = 'UnhandledRejection';
  } else {
    message = 'Unhandled promise rejection';
    name = 'UnhandledRejection';
    try {
      message = JSON.stringify(reason);
    } catch {
      // Ignore serialization errors
    }
  }

  const capturedError: CapturedError = {
    message,
    name,
    stack: sanitizeStack(stack),
    type: 'unhandled_rejection',
    timestamp: Date.now(),
    context: {},
  };

  recordError(capturedError);
  state.errorCallback?.(capturedError);
}

/**
 * Record an error to OpenTelemetry
 */
function recordError(error: CapturedError): void {
  try {
    const tracer = getTracer();
    const spanAttributes = getSpanAttributes();

    const span = tracer.startSpan('error', {
      kind: SpanKind.INTERNAL,
      attributes: {
        ...spanAttributes,
        'error.type': error.type,
        'error.message': error.message,
        'error.name': error.name,
        'error.stack': error.stack || '',
        'error.filename': error.filename || '',
        'error.lineno': error.lineno || 0,
        'error.colno': error.colno || 0,
      },
      startTime: error.timestamp,
    });

    span.setStatus({ code: SpanStatusCode.ERROR, message: error.message });
    span.end(error.timestamp);
  } catch (e) {
    // Don't throw errors from error handling
    console.error('[FoundationMetrics] Error recording error:', e);
  }
}

/**
 * Manually capture an error
 */
export function captureError(error: Error, context?: ErrorContext): CapturedError {
  const capturedError: CapturedError = {
    message: error.message,
    name: error.name,
    stack: sanitizeStack(error.stack),
    type: context?.type || 'custom',
    timestamp: Date.now(),
    context: context || {},
  };

  recordError(capturedError);
  state?.errorCallback?.(capturedError);

  return capturedError;
}

/**
 * Create an error handler for React Error Boundaries
 */
export function createErrorBoundaryHandler(componentName: string) {
  return (error: Error, errorInfo: { componentStack?: string }) => {
    const capturedError: CapturedError = {
      message: error.message,
      name: error.name,
      stack: sanitizeStack(error.stack),
      type: 'react_error_boundary',
      timestamp: Date.now(),
      context: {
        type: 'react_error_boundary',
        componentName,
        metadata: {
          componentStack: errorInfo.componentStack,
        },
      },
    };

    recordError(capturedError);
    state?.errorCallback?.(capturedError);
  };
}

/**
 * Sanitize stack trace
 */
function sanitizeStack(stack?: string): string {
  if (!stack) {
    return '';
  }
  return stack;
}

/**
 * Get resource URL from element
 */
function getResourceUrl(element: HTMLElement): string {
  if (element instanceof HTMLScriptElement) {
    return element.src;
  }
  if (element instanceof HTMLLinkElement) {
    return element.href;
  }
  if (element instanceof HTMLImageElement) {
    return element.src;
  }
  if (element instanceof HTMLAudioElement || element instanceof HTMLVideoElement) {
    return element.src;
  }
  if (element instanceof HTMLSourceElement) {
    return element.src;
  }
  if (element instanceof HTMLTrackElement) {
    return element.src;
  }
  if (element instanceof HTMLEmbedElement) {
    return element.src;
  }
  if (element instanceof HTMLIFrameElement) {
    return element.src;
  }
  return 'unknown';
}

/**
 * Check if error instrumentation is installed
 */
export function isErrorInstrumentationInstalled(): boolean {
  return state?.isInstalled ?? false;
}
