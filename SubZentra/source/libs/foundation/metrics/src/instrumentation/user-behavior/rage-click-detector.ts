/**
 * Rage Click Detection
 * @module instrumentation/user-behavior/rage-click-detector
 */

import { getCurrentRoute } from '@open-zentra/foundation-utils';

import { getSpanAttributes } from '../../core/context-manager';
import { getMeter } from '../../core/otel-provider';
import type { RageClickEvent, UserBehaviorSignalConfig } from '../../types';

/**
 * Click record for rage detection
 */
interface ClickRecord {
  x: number;
  y: number;
  timestamp: number;
  target: HTMLElement;
}

/**
 * Rage click detector state
 */
interface RageClickDetectorState {
  config: UserBehaviorSignalConfig;
  isInstalled: boolean;
  clickHistory: ClickRecord[];
  callback?: (event: RageClickEvent) => void;
}

let state: RageClickDetectorState | null = null;

/**
 * Distance threshold (pixels) for clicks to be considered "same area"
 */
const CLICK_DISTANCE_THRESHOLD = 50;

/**
 * Install rage click detection
 */
export function installRageClickDetection(
  config: UserBehaviorSignalConfig,
  callback?: (event: RageClickEvent) => void,
): void {
  if (typeof window === 'undefined') {
    return;
  }

  if (state?.isInstalled) {
    console.warn('[FoundationMetrics] Rage click detection already installed');
    return;
  }

  state = {
    config,
    isInstalled: false,
    clickHistory: [],
    callback,
  };

  if (!config.detectRageClicks) {
    return;
  }

  // Add click listener
  document.addEventListener('click', handleClickForRageDetection, {
    capture: true,
    passive: true,
  });

  state.isInstalled = true;
}

/**
 * Uninstall rage click detection
 */
export function uninstallRageClickDetection(): void {
  if (typeof document !== 'undefined') {
    document.removeEventListener('click', handleClickForRageDetection, {
      capture: true,
    });
  }
  state = null;
}

/**
 * Handle click for rage detection
 */
function handleClickForRageDetection(event: MouseEvent): void {
  if (!state?.config.enabled) {
    return;
  }

  const target = event.target;
  if (!(target instanceof HTMLElement)) {
    return;
  }

  const now = Date.now();
  const { rageClickThreshold = 3, rageClickWindow = 1000 } = state.config;

  // Add click to history
  state.clickHistory.push({
    x: event.clientX,
    y: event.clientY,
    timestamp: now,
    target,
  });

  // Remove old clicks outside the window
  state.clickHistory = state.clickHistory.filter(
    (click) => now - click.timestamp <= rageClickWindow,
  );

  // Check for rage click
  const nearbyClicks = state.clickHistory.filter((click) => {
    const distance = Math.sqrt(
      Math.pow(click.x - event.clientX, 2) + Math.pow(click.y - event.clientY, 2),
    );
    return distance <= CLICK_DISTANCE_THRESHOLD;
  });

  if (nearbyClicks.length >= rageClickThreshold) {
    // Rage click detected!
    const rageClickEvent: RageClickEvent = {
      clickCount: nearbyClicks.length,
      targetSelector: getTargetSelector(target),
      targetOzid: target.getAttribute('data-ozid') || undefined,
      windowDuration: now - nearbyClicks[0].timestamp,
      firstClickTime: nearbyClicks[0].timestamp,
      lastClickTime: now,
      route: getCurrentRoute(),
    };

    recordRageClick(rageClickEvent);
    state.callback?.(rageClickEvent);

    // Clear history to prevent multiple triggers
    state.clickHistory = [];
  }
}

/**
 * Get a selector for the target element
 */
function getTargetSelector(element: HTMLElement): string {
  const parts: string[] = [];

  // Tag name
  parts.push(element.tagName.toLowerCase());

  // ID
  if (element.id) {
    return `#${element.id}`;
  }

  // Class names (first 2)
  if (element.className) {
    const classes = element.className.split(' ').filter(Boolean).slice(0, 2);
    if (classes.length > 0) {
      parts.push(`.${classes.join('.')}`);
    }
  }

  // data-ozid
  const ozid = element.getAttribute('data-ozid');
  if (ozid) {
    parts.push(`[data-ozid="${ozid}"]`);
  }

  return parts.join('');
}

/**
 * Record rage click event to OpenTelemetry
 */
function recordRageClick(event: RageClickEvent): void {
  try {
    const meter = getMeter();
    const spanAttributes = getSpanAttributes();

    // Rage click counter
    const rageClickCounter = meter.createCounter('rage_clicks_total', {
      description: 'Total number of rage clicks detected',
    });

    rageClickCounter.add(1, {
      ...spanAttributes,
      'rage_click.count': event.clickCount,
      'rage_click.target': event.targetSelector,
      'rage_click.target_ozid': event.targetOzid || 'unknown',
      'page.route': event.route,
    });

    // Also record as a histogram for analysis
    const rageClickHistogram = meter.createHistogram('rage_click_count', {
      description: 'Number of clicks in rage click events',
    });

    rageClickHistogram.record(event.clickCount, {
      ...spanAttributes,
      'page.route': event.route,
    });
  } catch (e) {
    console.error('[FoundationMetrics] Error recording rage click:', e);
  }
}

/**
 * Manually report a rage click (for custom detection)
 */
export function reportRageClick(
  targetSelector: string,
  clickCount: number,
  targetOzid?: string,
): void {
  if (!state?.config.enabled) {
    return;
  }

  const now = Date.now();
  const event: RageClickEvent = {
    clickCount,
    targetSelector,
    targetOzid,
    windowDuration: 0,
    firstClickTime: now,
    lastClickTime: now,
    route: getCurrentRoute(),
  };

  recordRageClick(event);
  state.callback?.(event);
}

/**
 * Check if rage click detection is installed
 */
export function isRageClickDetectionInstalled(): boolean {
  return state?.isInstalled ?? false;
}

/**
 * Get current click history (for debugging)
 */
export function getClickHistory(): ClickRecord[] {
  return state?.clickHistory ?? [];
}

/**
 * Clear click history
 */
export function clearClickHistory(): void {
  if (state) {
    state.clickHistory = [];
  }
}
