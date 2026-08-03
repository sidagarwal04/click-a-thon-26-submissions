/**
 * SPA Navigation Instrumentation
 * @module instrumentation/performance/spa-navigation
 */

import { SpanKind } from '@opentelemetry/api';

import { getCurrentRoute } from '@open-zentra/foundation-utils';

import { getSpanAttributes } from '../../core/context-manager';
import { getMeter, getTracer } from '../../core/otel-provider';
import type { PerformanceSignalConfig, SPANavigationEvent, SpaNavigationType } from '../../types';
import { SPA_NAVIGATION_TYPE } from '../../types/constants';

/**
 * SPA navigation instrumentation state
 */
interface SPANavigationState {
  config: PerformanceSignalConfig;
  isInstalled: boolean;
  currentRoute: string;
  navigationStartTime: number;
  callback?: (event: SPANavigationEvent) => void;
}

let state: SPANavigationState | null = null;

/**
 * Install SPA navigation instrumentation
 */
export function installSPANavigationInstrumentation(
  config: PerformanceSignalConfig,
  callback?: (event: SPANavigationEvent) => void,
): void {
  if (typeof window === 'undefined') {
    return;
  }

  if (state?.isInstalled) {
    console.warn('[FoundationMetrics] SPA navigation instrumentation already installed');
    return;
  }

  state = {
    config,
    isInstalled: false,
    currentRoute: getCurrentRoute(),
    navigationStartTime: performance.now(),
    callback,
  };

  if (!config.spaNavigation) {
    return;
  }

  // Patch History API
  patchHistoryAPI();

  // Listen for popstate events (back/forward navigation)
  window.addEventListener('popstate', handlePopState);

  state.isInstalled = true;
}

/**
 * Uninstall SPA navigation instrumentation
 */
export function uninstallSPANavigationInstrumentation(): void {
  if (typeof window !== 'undefined') {
    window.removeEventListener('popstate', handlePopState);
  }

  // Note: We don't restore the original History API methods
  // as other code may depend on our patched versions

  state = null;
}

/**
 * Patch the History API to intercept navigation
 */
function patchHistoryAPI(): void {
  if (typeof window === 'undefined' || typeof window.history === 'undefined') {
    return;
  }

  const historyApi = window.history;
  const originalPushState = historyApi.pushState.bind(historyApi);
  const originalReplaceState = historyApi.replaceState.bind(historyApi);

  historyApi.pushState = function (data: unknown, unused: string, url?: string | URL | null) {
    handleNavigation(SPA_NAVIGATION_TYPE.PUSH, url);
    return originalPushState(data, unused, url);
  };

  historyApi.replaceState = function (data: unknown, unused: string, url?: string | URL | null) {
    handleNavigation(SPA_NAVIGATION_TYPE.REPLACE, url);
    return originalReplaceState(data, unused, url);
  };
}

/**
 * Handle popstate events
 */
function handlePopState(): void {
  handleNavigation(SPA_NAVIGATION_TYPE.POP);
}

/**
 * Handle navigation events
 */
function handleNavigation(type: SpaNavigationType, url?: string | URL | null): void {
  if (!state?.config.enabled) {
    return;
  }

  const previousRoute = state.currentRoute;
  const now = performance.now();
  const duration = now - state.navigationStartTime;

  // Update state
  const newRoute = url
    ? new URL(url.toString(), window.location.origin).pathname
    : getCurrentRoute();
  state.currentRoute = newRoute;
  state.navigationStartTime = now;

  // Skip if route hasn't changed (e.g., query param changes)
  if (previousRoute === newRoute) {
    return;
  }

  const event: SPANavigationEvent = {
    type,
    from: previousRoute,
    to: newRoute,
    duration,
    timestamp: Date.now(),
  };

  recordSPANavigation(event);
  state.callback?.(event);
}

/**
 * Record SPA navigation to OpenTelemetry
 */
function recordSPANavigation(event: SPANavigationEvent): void {
  try {
    const tracer = getTracer();
    const meter = getMeter();
    const spanAttributes = getSpanAttributes();

    // Create a span for the navigation
    const span = tracer.startSpan('spa_navigation', {
      kind: SpanKind.INTERNAL,
      attributes: {
        ...spanAttributes,
        'navigation.type': event.type,
        'navigation.from': event.from,
        'navigation.to': event.to,
        'navigation.duration_ms': event.duration,
      },
    });
    span.end();

    // Record navigation duration metric
    const navigationHistogram = meter.createHistogram('spa_navigation_duration_ms', {
      description: 'SPA navigation duration in milliseconds',
      unit: 'ms',
    });

    navigationHistogram.record(event.duration, {
      ...spanAttributes,
      'navigation.type': event.type,
      'page.route': event.to,
      'page.previous_route': event.from,
    });

    // Count navigations
    const navigationCounter = meter.createCounter('spa_navigation_count', {
      description: 'Number of SPA navigations',
    });

    navigationCounter.add(1, {
      ...spanAttributes,
      'navigation.type': event.type,
      'page.route': event.to,
    });
  } catch (e) {
    console.error('[FoundationMetrics] Error recording SPA navigation:', e);
  }
}

/**
 * Manually track a navigation (for frameworks with custom routers)
 */
export function trackNavigation(to: string, from?: string): void {
  if (!state?.config.enabled) {
    return;
  }

  const now = performance.now();
  const duration = now - state.navigationStartTime;
  const previousRoute = from || state.currentRoute;

  state.currentRoute = to;
  state.navigationStartTime = now;

  const event: SPANavigationEvent = {
    type: SPA_NAVIGATION_TYPE.PUSH,
    from: previousRoute,
    to,
    duration,
    timestamp: Date.now(),
  };

  recordSPANavigation(event);
  state.callback?.(event);
}

/**
 * Get current route
 */
export function getCurrentTrackedRoute(): string {
  return state?.currentRoute ?? getCurrentRoute();
}

/**
 * Check if SPA navigation instrumentation is installed
 */
export function isSPANavigationInstalled(): boolean {
  return state?.isInstalled ?? false;
}
