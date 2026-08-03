/**
 * Web Vitals Instrumentation
 * @module instrumentation/performance/web-vitals
 */

import { onCLS, onFCP, onINP, onLCP, onTTFB, type Metric } from 'web-vitals';

import { getCurrentRoute } from '@open-zentra/foundation-utils';

import { getSpanAttributes } from '../../core/context-manager';
import { getMeter } from '../../core/otel-provider';
import type {
  PerformanceSignalConfig,
  WebVitalMetric,
  WebVitalName,
  WebVitalRating,
} from '../../types';

/**
 * Web vitals instrumentation state
 */
interface WebVitalsState {
  config: PerformanceSignalConfig;
  isInstalled: boolean;
  callback?: (metric: WebVitalMetric) => void;
}

let state: WebVitalsState | null = null;

// =============================================================================
// CACHED OTEL INSTRUMENTS
// =============================================================================

/**
 * Cached OTel instruments to avoid recreating on every measurement.
 * Instruments are created lazily on first use and reused thereafter.
 */
interface CachedInstruments {
  webVitalHistograms: Map<string, ReturnType<ReturnType<typeof getMeter>['createHistogram']>>;
  combinedHistogram: ReturnType<ReturnType<typeof getMeter>['createHistogram']> | null;
}

const cachedInstruments: CachedInstruments = {
  webVitalHistograms: new Map(),
  combinedHistogram: null,
};

/**
 * Get or create a cached histogram for a specific web vital metric.
 */
const getWebVitalHistogram = (metricName: string) => {
  const key = metricName.toLowerCase();
  let histogram = cachedInstruments.webVitalHistograms.get(key);
  if (!histogram) {
    const meter = getMeter();
    histogram = meter.createHistogram(`web_vital_${key}`, {
      description: `Web Vital ${metricName} measurement`,
      unit: metricName === 'CLS' ? '' : 'ms',
    });
    cachedInstruments.webVitalHistograms.set(key, histogram);
  }
  return histogram;
};

/**
 * Get or create the cached combined web vitals histogram.
 */
const getCombinedHistogram = () => {
  if (!cachedInstruments.combinedHistogram) {
    const meter = getMeter();
    cachedInstruments.combinedHistogram = meter.createHistogram('web_vitals', {
      description: 'All Web Vitals measurements',
    });
  }
  return cachedInstruments.combinedHistogram;
};

/**
 * Install web vitals instrumentation
 */
export function installWebVitalsInstrumentation(
  config: PerformanceSignalConfig,
  callback?: (metric: WebVitalMetric) => void,
): void {
  if (typeof window === 'undefined') {
    return;
  }

  if (state?.isInstalled) {
    console.warn('[FoundationMetrics] Web Vitals instrumentation already installed');
    return;
  }

  state = {
    config,
    isInstalled: false,
    callback,
  };

  if (!config.webVitals) {
    return;
  }

  // Install all web vitals listeners
  onLCP(handleMetric);
  onCLS(handleMetric);
  onINP(handleMetric);
  onFCP(handleMetric);
  onTTFB(handleMetric);

  state.isInstalled = true;
}

/**
 * Uninstall web vitals instrumentation
 */
export function uninstallWebVitalsInstrumentation(): void {
  // web-vitals library doesn't support unsubscribing
  // Clear state and instrument cache
  state = null;
  cachedInstruments.webVitalHistograms.clear();
  cachedInstruments.combinedHistogram = null;
}

const VALID_WEB_VITAL_NAMES = new Set<string>(['LCP', 'CLS', 'INP', 'FCP', 'TTFB', 'FID']);
const VALID_RATINGS = new Set<string>(['good', 'needs-improvement', 'poor']);
const VALID_NAV_TYPES = new Set<string>([
  'navigate',
  'reload',
  'back-forward',
  'back-forward-cache',
  'prerender',
]);

function isWebVitalName(name: string): name is WebVitalName {
  return VALID_WEB_VITAL_NAMES.has(name);
}

function isWebVitalRating(rating: string): rating is WebVitalRating {
  return VALID_RATINGS.has(rating);
}

function isNavigationType(type: string | undefined): type is WebVitalMetric['navigationType'] {
  return type === undefined || VALID_NAV_TYPES.has(type);
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function getMetricAttribution(metric: Metric): Record<string, unknown> | undefined {
  // Check if metric has attribution property with correct shape
  if ('attribution' in metric && isRecord(metric.attribution)) {
    return metric.attribution;
  }
  return undefined;
}

/**
 * Handle a web vital metric
 */
function handleMetric(metric: Metric): void {
  if (!state?.config.enabled) {
    return;
  }

  // Validate metric name
  if (!isWebVitalName(metric.name)) {
    console.warn(`[FoundationMetrics] Unknown web vital name: ${metric.name}`);
    return;
  }

  // Validate rating
  if (!isWebVitalRating(metric.rating)) {
    console.warn(`[FoundationMetrics] Unknown web vital rating: ${metric.rating}`);
    return;
  }

  // Get attribution safely
  const attribution = getMetricAttribution(metric);

  const webVitalMetric: WebVitalMetric = {
    name: metric.name,
    value: metric.value,
    rating: metric.rating,
    delta: metric.delta,
    id: metric.id,
    navigationType: isNavigationType(metric.navigationType) ? metric.navigationType : undefined,
    attribution,
  };

  // Record to OpenTelemetry
  recordWebVital(webVitalMetric);

  // Call callback
  state.callback?.(webVitalMetric);
}

/**
 * Record a web vital metric to OpenTelemetry
 */
function recordWebVital(metric: WebVitalMetric): void {
  try {
    const spanAttributes = getSpanAttributes();
    const route = getCurrentRoute();

    // Use cached histogram for the specific metric
    const histogram = getWebVitalHistogram(metric.name);

    histogram.record(metric.value, {
      ...spanAttributes,
      'web_vital.name': metric.name,
      'web_vital.rating': metric.rating,
      'web_vital.navigation_type': metric.navigationType || 'unknown',
      'page.route': route,
    });

    // Use cached combined histogram for easier querying
    const combinedHistogram = getCombinedHistogram();

    combinedHistogram.record(metric.value, {
      ...spanAttributes,
      'metric.name': metric.name,
      'metric.rating': metric.rating,
      'navigation.type': metric.navigationType || 'unknown',
      'page.route': route,
    });
  } catch (e) {
    console.error('[FoundationMetrics] Error recording web vital:', e);
  }
}

/**
 * Manually record a web vital (for custom measurements)
 */
export function measureWebVital(metric: WebVitalMetric): void {
  recordWebVital(metric);
  state?.callback?.(metric);
}

/**
 * Get web vital thresholds
 */
export function getWebVitalThresholds(): Record<
  WebVitalName,
  { good: number; needsImprovement: number }
> {
  return {
    LCP: { good: 2500, needsImprovement: 4000 },
    CLS: { good: 0.1, needsImprovement: 0.25 },
    INP: { good: 200, needsImprovement: 500 },
    FCP: { good: 1800, needsImprovement: 3000 },
    TTFB: { good: 800, needsImprovement: 1800 },
    FID: { good: 100, needsImprovement: 300 }, // Legacy, replaced by INP
  };
}

/**
 * Calculate rating from value
 */
export function calculateRating(name: WebVitalName, value: number): WebVitalRating {
  const thresholds = getWebVitalThresholds()[name];
  if (!thresholds) {
    return 'needs-improvement';
  }

  if (value <= thresholds.good) {
    return 'good';
  }
  if (value <= thresholds.needsImprovement) {
    return 'needs-improvement';
  }
  return 'poor';
}

/**
 * Check if web vitals instrumentation is installed
 */
export function isWebVitalsInstalled(): boolean {
  return state?.isInstalled ?? false;
}
