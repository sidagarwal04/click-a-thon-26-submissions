/**
 * Feature Flag Utilities
 * @module utils/feature-flags
 */

import type { SignalsConfig } from '../types';

/**
 * Feature flag state
 */
export interface FeatureFlags {
  errors: boolean;
  performance: boolean;
  network: boolean;
  userBehavior: boolean;
  webVitals: boolean;
  longTasks: boolean;
  spaNavigation: boolean;
  clickTracking: boolean;
  rageClickDetection: boolean;
  sessionTracking: boolean;
}

/**
 * Extract feature flags from signals configuration
 */
export const extractFeatureFlags = (signals: SignalsConfig): FeatureFlags => {
  const errorConfig =
    typeof signals.errors === 'boolean' ? { enabled: signals.errors } : signals.errors;

  const perfConfig =
    typeof signals.performance === 'boolean'
      ? { enabled: signals.performance, webVitals: true, longTasks: true, spaNavigation: true }
      : signals.performance;

  const networkConfig =
    typeof signals.network === 'boolean' ? { enabled: signals.network } : signals.network;

  const behaviorConfig =
    typeof signals.userBehavior === 'boolean'
      ? {
          enabled: signals.userBehavior,
          trackClicks: true,
          detectRageClicks: true,
          trackSession: true,
        }
      : signals.userBehavior;

  return {
    errors: errorConfig.enabled,
    performance: perfConfig.enabled,
    network: networkConfig.enabled,
    userBehavior: behaviorConfig.enabled,
    webVitals: perfConfig.enabled && perfConfig.webVitals,
    longTasks: perfConfig.enabled && perfConfig.longTasks,
    spaNavigation: perfConfig.enabled && perfConfig.spaNavigation,
    clickTracking: behaviorConfig.enabled && behaviorConfig.trackClicks,
    rageClickDetection: behaviorConfig.enabled && behaviorConfig.detectRageClicks,
    sessionTracking: behaviorConfig.enabled && behaviorConfig.trackSession,
  };
};

/**
 * Check if a specific feature is enabled
 */
export const isFeatureEnabled = (flags: FeatureFlags, feature: keyof FeatureFlags): boolean =>
  flags[feature] ?? false;

/**
 * Create a feature flag checker function
 */
export const createFeatureChecker =
  (flags: FeatureFlags) =>
  (feature: keyof FeatureFlags): boolean =>
    isFeatureEnabled(flags, feature);
