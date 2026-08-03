/**
 * Foundation Metrics
 *
 * Enterprise-grade frontend observability library using OpenTelemetry.
 *
 * @packageDocumentation
 */

// ============================================
// Core SDK
// ============================================
export {
  FoundationMetrics,
  init,
  reinitialize,
  getInstance,
  isInitialized,
  getLifecycleState,
} from './core';

// ============================================
// Types
// ============================================
export * from './types';

// ============================================
// Instrumentation
// ============================================
export {
  // Errors
  installErrorInstrumentation,
  uninstallErrorInstrumentation,
  captureError,
  createErrorBoundaryHandler,
  // Performance
  installWebVitalsInstrumentation,
  installPageLoadInstrumentation,
  installSPANavigationInstrumentation,
  installLongTasksInstrumentation,
  measureWebVital,
  trackNavigation,
  reportLongTask,
  measureTask,
  // Network
  installFetchInstrumentation,
  installXHRInstrumentation,
  createRetryFetch,
  // User behavior
  installClickTracking,
  installRageClickDetection,
  installNavigationTracking,
  installSessionManager,
  trackClick,
  reportRageClick,
  trackPageNavigation,
  getCurrentSession,
  getSessionId,
} from './instrumentation';

// ============================================
// Compliance
// ============================================
export {
  createPIIScrubber,
  createDefaultScrubber,
  scrubUrl,
  scrubHeaders,
  createFieldFilter,
  createAttributesFilter,
} from './compliance';

// ============================================
// Sampling
// ============================================
export {
  createHeadSampler,
  createPrioritySampler,
  createConsistentSampler,
  createRateLimiter,
  createTokenBucketLimiter,
  createKeyedRateLimiter,
} from './sampling';

// ============================================
// Plugins
// ============================================
export { createPluginManager, getPluginManager } from './plugins';

// ============================================
// Feature Flags (Metrics-specific)
// ============================================
export {
  extractFeatureFlags,
  isFeatureEnabled,
  createFeatureChecker,
  type FeatureFlags,
} from './utils/feature-flags';

// ============================================
// NOTE: Common utilities (browser detection, URL handling, etc.)
// should be imported directly from @open-zentra/foundation-utils
// Re-exports have been removed to reduce bundle size and clarify dependencies.
// ============================================
