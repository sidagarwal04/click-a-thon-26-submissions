/**
 * Long Tasks Instrumentation
 * @module instrumentation/performance/long-tasks
 */

import { getCurrentRoute } from '@open-zentra/foundation-utils';

import { getSpanAttributes } from '../../core/context-manager';
import { getMeter } from '../../core/otel-provider';
import type { LongTaskEntry, PerformanceSignalConfig } from '../../types';

/**
 * Long tasks instrumentation state
 */
interface LongTasksState {
  config: PerformanceSignalConfig;
  isInstalled: boolean;
  observer: PerformanceObserver | null;
  callback?: (entry: LongTaskEntry) => void;
}

let state: LongTasksState | null = null;

/**
 * Install long tasks instrumentation
 */
export function installLongTasksInstrumentation(
  config: PerformanceSignalConfig,
  callback?: (entry: LongTaskEntry) => void,
): void {
  if (typeof window === 'undefined' || typeof PerformanceObserver === 'undefined') {
    return;
  }

  if (state?.isInstalled) {
    console.warn('[FoundationMetrics] Long tasks instrumentation already installed');
    return;
  }

  state = {
    config,
    isInstalled: false,
    observer: null,
    callback,
  };

  if (!config.longTasks) {
    return;
  }

  // Check if longtask is supported
  if (!isLongTaskSupported()) {
    console.warn('[FoundationMetrics] Long Task API not supported in this browser');
    return;
  }

  // Create PerformanceObserver
  try {
    state.observer = new PerformanceObserver(handleLongTasks);
    state.observer.observe({ entryTypes: ['longtask'] });
    state.isInstalled = true;
  } catch (e) {
    console.warn('[FoundationMetrics] Failed to install long tasks observer:', e);
  }
}

/**
 * Uninstall long tasks instrumentation
 */
export function uninstallLongTasksInstrumentation(): void {
  if (state?.observer) {
    state.observer.disconnect();
  }
  state = null;
}

/**
 * Check if Long Task API is supported
 */
function isLongTaskSupported(): boolean {
  try {
    return PerformanceObserver.supportedEntryTypes.includes('longtask');
  } catch {
    return false;
  }
}

/**
 * Handle long task entries
 */
function handleLongTasks(list: PerformanceObserverEntryList): void {
  if (!state?.config.enabled) {
    return;
  }

  const threshold = state.config.longTaskThreshold || 50;

  for (const entry of list.getEntries()) {
    // Skip if below threshold (shouldn't happen for longtask, but just in case)
    if (entry.duration < threshold) {
      continue;
    }

    const longTaskEntry: LongTaskEntry = {
      duration: entry.duration,
      startTime: entry.startTime,
      name: entry.name,
      attribution: getTaskAttribution(entry),
    };

    recordLongTask(longTaskEntry);
    state.callback?.(longTaskEntry);
  }
}

/**
 * Check if entry is a PerformanceLongTaskTiming
 */
function isLongTaskTiming(entry: PerformanceEntry): entry is PerformanceLongTaskTiming {
  return entry.entryType === 'longtask' && 'attribution' in entry;
}

/**
 * Get attribution for a long task
 */
function getTaskAttribution(entry: PerformanceEntry): LongTaskEntry['attribution'] {
  if (!isLongTaskTiming(entry) || !entry.attribution) {
    return [];
  }

  return entry.attribution.map((attr) => ({
    containerType: attr.containerType,
    containerSrc: attr.containerSrc,
    containerId: attr.containerId,
    containerName: attr.containerName,
  }));
}

/**
 * Long task attribution interface (not in all TypeScript libs)
 */
interface TaskAttributionTiming {
  containerType: string;
  containerSrc: string;
  containerId: string;
  containerName: string;
}

interface PerformanceLongTaskTiming extends PerformanceEntry {
  attribution: TaskAttributionTiming[];
}

/**
 * Record a long task to OpenTelemetry
 */
function recordLongTask(entry: LongTaskEntry): void {
  try {
    const meter = getMeter();
    const spanAttributes = getSpanAttributes();
    const route = getCurrentRoute();

    // Record long task duration
    const histogram = meter.createHistogram('long_task_duration_ms', {
      description: 'Long task duration in milliseconds',
      unit: 'ms',
    });

    histogram.record(entry.duration, {
      ...spanAttributes,
      'page.route': route,
      'task.name': entry.name,
    });

    // Count long tasks
    const counter = meter.createCounter('long_task_count', {
      description: 'Number of long tasks',
    });

    counter.add(1, {
      ...spanAttributes,
      'page.route': route,
    });

    // Track total blocking time (sum of all long task time over 50ms)
    const blockingTime = entry.duration - 50; // Only count time over threshold
    if (blockingTime > 0) {
      const tbtHistogram = meter.createHistogram('total_blocking_time_ms', {
        description: 'Total blocking time in milliseconds',
        unit: 'ms',
      });

      tbtHistogram.record(blockingTime, {
        ...spanAttributes,
        'page.route': route,
      });
    }
  } catch (e) {
    console.error('[FoundationMetrics] Error recording long task:', e);
  }
}

/**
 * Manually report a long task (for custom blocking operations)
 */
export function reportLongTask(duration: number, name = 'custom-long-task'): void {
  if (!state?.config.enabled) {
    return;
  }

  const entry: LongTaskEntry = {
    duration,
    startTime: performance.now() - duration,
    name,
    attribution: [],
  };

  recordLongTask(entry);
  state.callback?.(entry);
}

/**
 * Measure a function execution and report if it's a long task
 */
export async function measureTask<T>(name: string, fn: () => T | Promise<T>): Promise<T> {
  const start = performance.now();

  try {
    const result = await fn();
    return result;
  } finally {
    const duration = performance.now() - start;
    const threshold = state?.config.longTaskThreshold || 50;

    if (duration >= threshold) {
      reportLongTask(duration, name);
    }
  }
}

/**
 * Check if long tasks instrumentation is installed
 */
export function isLongTasksInstalled(): boolean {
  return state?.isInstalled ?? false;
}
