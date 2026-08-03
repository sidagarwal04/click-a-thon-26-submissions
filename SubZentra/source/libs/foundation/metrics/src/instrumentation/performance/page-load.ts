/**
 * Page Load Timing Instrumentation
 * @module instrumentation/performance/page-load
 */

import { SpanKind } from '@opentelemetry/api';

import { getCurrentPageUrl, getCurrentRoute } from '@open-zentra/foundation-utils';

import { getSpanAttributes } from '../../core/context-manager';
import { getMeter, getTracer } from '../../core/otel-provider';
import type { PageLoadTiming, PerformanceSignalConfig } from '../../types';

/**
 * Page load instrumentation state
 */
interface PageLoadState {
  config: PerformanceSignalConfig;
  isInstalled: boolean;
  timing: PageLoadTiming | null;
  callback?: (timing: PageLoadTiming) => void;
}

let state: PageLoadState | null = null;

/**
 * Install page load timing instrumentation
 */
export function installPageLoadInstrumentation(
  config: PerformanceSignalConfig,
  callback?: (timing: PageLoadTiming) => void,
): void {
  if (typeof window === 'undefined' || typeof performance === 'undefined') {
    return;
  }

  if (state?.isInstalled) {
    console.warn('[FoundationMetrics] Page load instrumentation already installed');
    return;
  }

  state = {
    config,
    isInstalled: false,
    timing: null,
    callback,
  };

  if (!config.pageLoad) {
    return;
  }

  // Wait for page to fully load
  if (document.readyState === 'complete') {
    capturePageLoadTiming();
  } else {
    window.addEventListener('load', capturePageLoadTiming, { once: true });
  }

  state.isInstalled = true;
}

/**
 * Uninstall page load instrumentation
 */
export function uninstallPageLoadInstrumentation(): void {
  if (typeof window !== 'undefined') {
    window.removeEventListener('load', capturePageLoadTiming);
  }
  state = null;
}

/**
 * Capture page load timing
 */
function capturePageLoadTiming(): void {
  if (!state?.config.enabled) {
    return;
  }

  // Use a small delay to ensure all timing data is available
  setTimeout(() => {
    const timing = getPageLoadTiming();
    if (timing) {
      state!.timing = timing;
      recordPageLoadTiming(timing);
      state?.callback?.(timing);
    }
  }, 0);
}

/**
 * Check if entry is a PerformanceNavigationTiming
 */
function isNavigationTiming(entry: PerformanceEntry): entry is PerformanceNavigationTiming {
  return entry.entryType === 'navigation' && 'domInteractive' in entry;
}

/**
 * Get page load timing from Navigation Timing API
 */
function getPageLoadTiming(): PageLoadTiming | null {
  if (typeof performance === 'undefined') {
    return null;
  }

  const entries = performance.getEntriesByType('navigation');
  if (entries.length === 0) {
    return null;
  }

  const nav = entries[0];
  if (!isNavigationTiming(nav)) {
    return null;
  }

  return {
    dnsLookup: nav.domainLookupEnd - nav.domainLookupStart,
    tcpConnection: nav.connectEnd - nav.connectStart,
    tlsNegotiation: nav.secureConnectionStart > 0 ? nav.connectEnd - nav.secureConnectionStart : 0,
    ttfb: nav.responseStart - nav.requestStart,
    contentDownload: nav.responseEnd - nav.responseStart,
    domInteractive: nav.domInteractive - nav.startTime,
    domContentLoaded: nav.domContentLoadedEventEnd - nav.startTime,
    loadComplete: nav.loadEventEnd - nav.startTime,
  };
}

/**
 * Record page load timing to OpenTelemetry
 */
function recordPageLoadTiming(timing: PageLoadTiming): void {
  try {
    const tracer = getTracer();
    const meter = getMeter();
    const spanAttributes = getSpanAttributes();
    const route = getCurrentRoute();
    const url = getCurrentPageUrl();

    // Create a span for the page load
    const span = tracer.startSpan('page_load', {
      kind: SpanKind.INTERNAL,
      attributes: {
        ...spanAttributes,
        'page.url': url,
        'page.route': route,
        'timing.dns_lookup_ms': timing.dnsLookup,
        'timing.tcp_connection_ms': timing.tcpConnection,
        'timing.tls_negotiation_ms': timing.tlsNegotiation,
        'timing.ttfb_ms': timing.ttfb,
        'timing.content_download_ms': timing.contentDownload,
        'timing.dom_interactive_ms': timing.domInteractive,
        'timing.dom_content_loaded_ms': timing.domContentLoaded,
        'timing.load_complete_ms': timing.loadComplete,
      },
    });
    span.end();

    // Record individual metrics
    const pageLoadHistogram = meter.createHistogram('page_load_time_ms', {
      description: 'Page load time in milliseconds',
      unit: 'ms',
    });

    pageLoadHistogram.record(timing.loadComplete, {
      ...spanAttributes,
      'page.route': route,
    });

    // Record TTFB separately as it's a key metric
    const ttfbHistogram = meter.createHistogram('ttfb_ms', {
      description: 'Time to First Byte in milliseconds',
      unit: 'ms',
    });

    ttfbHistogram.record(timing.ttfb, {
      ...spanAttributes,
      'page.route': route,
    });

    // Record DOM Content Loaded
    const dclHistogram = meter.createHistogram('dom_content_loaded_ms', {
      description: 'DOM Content Loaded time in milliseconds',
      unit: 'ms',
    });

    dclHistogram.record(timing.domContentLoaded, {
      ...spanAttributes,
      'page.route': route,
    });
  } catch (e) {
    console.error('[FoundationMetrics] Error recording page load timing:', e);
  }
}

/**
 * Manually capture page load timing (for SPA initial load)
 */
export function captureInitialPageLoad(): PageLoadTiming | null {
  const timing = getPageLoadTiming();
  if (timing) {
    recordPageLoadTiming(timing);
    state?.callback?.(timing);
  }
  return timing;
}

/**
 * Get the captured page load timing
 */
export function getPageLoadTimingData(): PageLoadTiming | null {
  return state?.timing ?? null;
}

/**
 * Check if page load instrumentation is installed
 */
export function isPageLoadInstalled(): boolean {
  return state?.isInstalled ?? false;
}
