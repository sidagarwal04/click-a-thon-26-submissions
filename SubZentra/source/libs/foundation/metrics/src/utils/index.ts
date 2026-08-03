/**
 * Metrics-specific Utilities
 * @module utils
 */

// Feature flag utilities
export {
  extractFeatureFlags,
  isFeatureEnabled,
  createFeatureChecker,
  type FeatureFlags,
} from './feature-flags';

// History API management (singleton)
export { HistoryManager, type HistoryCallback } from './history-manager';

// HTTP utilities for network instrumentation
export { isValidHttpMethod, toHttpMethod, recordNetworkMetrics } from './http-utils';

// Stack trace utilities
export { sanitizeStackTrace } from './stack-utils';
