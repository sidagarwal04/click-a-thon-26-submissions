/**
 * Navigation Tracking
 * @module instrumentation/user-behavior/navigation-tracker
 */

import { getCurrentRoute } from '@open-zentra/foundation-utils';

import { getSpanAttributes } from '../../core/context-manager';
import { getMeter } from '../../core/otel-provider';
import type { NavigationEvent, UserBehaviorSignalConfig } from '../../types';

/**
 * Navigation tracker state
 */
interface NavigationTrackerState {
  config: UserBehaviorSignalConfig;
  isInstalled: boolean;
  currentRoute: string;
  routeStartTime: number;
  callback?: (event: NavigationEvent) => void;
}

let state: NavigationTrackerState | null = null;

/**
 * Install navigation tracking
 */
export function installNavigationTracking(
  config: UserBehaviorSignalConfig,
  callback?: (event: NavigationEvent) => void,
): void {
  if (typeof window === 'undefined') {
    return;
  }

  if (state?.isInstalled) {
    console.warn('[FoundationMetrics] Navigation tracking already installed');
    return;
  }

  state = {
    config,
    isInstalled: false,
    currentRoute: getCurrentRoute(),
    routeStartTime: performance.now(),
    callback,
  };

  if (!config.trackNavigation) {
    return;
  }

  // Listen for popstate (back/forward)
  window.addEventListener('popstate', handlePopState);

  // Patch history methods
  patchHistoryMethods();

  state.isInstalled = true;
}

/**
 * Uninstall navigation tracking
 */
export function uninstallNavigationTracking(): void {
  if (typeof window !== 'undefined') {
    window.removeEventListener('popstate', handlePopState);
  }
  state = null;
}

/**
 * Patch history methods
 */
function patchHistoryMethods(): void {
  if (typeof window === 'undefined' || typeof window.history === 'undefined') {
    return;
  }

  const historyApi = window.history;
  const originalPushState = historyApi.pushState.bind(historyApi);
  const originalReplaceState = historyApi.replaceState.bind(historyApi);

  historyApi.pushState = function (...args) {
    const result = originalPushState(...args);
    handleNavigation();
    return result;
  };

  historyApi.replaceState = function (...args) {
    const result = originalReplaceState(...args);
    handleNavigation();
    return result;
  };
}

/**
 * Handle popstate event
 */
function handlePopState(): void {
  handleNavigation();
}

/**
 * Handle navigation
 */
function handleNavigation(): void {
  if (!state?.config.enabled) {
    return;
  }

  const newRoute = getCurrentRoute();
  const now = performance.now();

  // Skip if route hasn't changed
  if (newRoute === state.currentRoute) {
    return;
  }

  const timeOnPreviousPage = now - state.routeStartTime;

  const event: NavigationEvent = {
    from: state.currentRoute,
    to: newRoute,
    timestamp: Date.now(),
    timeOnPreviousPage,
  };

  // Update state
  state.currentRoute = newRoute;
  state.routeStartTime = now;

  recordNavigationEvent(event);
  state.callback?.(event);
}

/**
 * Record navigation event to OpenTelemetry
 */
function recordNavigationEvent(event: NavigationEvent): void {
  try {
    const meter = getMeter();
    const spanAttributes = getSpanAttributes();

    // Navigation counter
    const navigationCounter = meter.createCounter('user_navigations_total', {
      description: 'Total number of user navigations',
    });

    navigationCounter.add(1, {
      ...spanAttributes,
      'navigation.from': event.from || 'initial',
      'navigation.to': event.to,
    });

    // Time on page histogram
    if (event.timeOnPreviousPage !== undefined && event.from) {
      const timeOnPageHistogram = meter.createHistogram('time_on_page_ms', {
        description: 'Time spent on page in milliseconds',
        unit: 'ms',
      });

      timeOnPageHistogram.record(event.timeOnPreviousPage, {
        ...spanAttributes,
        'page.route': event.from,
      });
    }
  } catch (e) {
    console.error('[FoundationMetrics] Error recording navigation event:', e);
  }
}

/**
 * Manually track a navigation
 */
export function trackPageNavigation(to: string, from?: string): void {
  if (!state?.config.enabled) {
    return;
  }

  const now = performance.now();
  const timeOnPreviousPage = now - state.routeStartTime;

  const event: NavigationEvent = {
    from: from || state.currentRoute,
    to,
    timestamp: Date.now(),
    timeOnPreviousPage: from ? undefined : timeOnPreviousPage,
  };

  // Update state
  state.currentRoute = to;
  state.routeStartTime = now;

  recordNavigationEvent(event);
  state.callback?.(event);
}

/**
 * Get time on current page
 */
export function getTimeOnCurrentPage(): number {
  if (!state) {
    return 0;
  }
  return performance.now() - state.routeStartTime;
}

/**
 * Get current tracked route
 */
export function getCurrentTrackedRoute(): string {
  return state?.currentRoute ?? getCurrentRoute();
}

/**
 * Check if navigation tracking is installed
 */
export function isNavigationTrackingInstalled(): boolean {
  return state?.isInstalled ?? false;
}
