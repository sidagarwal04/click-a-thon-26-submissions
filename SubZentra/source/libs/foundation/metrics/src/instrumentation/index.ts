/**
 * Instrumentation Module Exports
 * @module instrumentation
 */

// Error instrumentation
export {
  installErrorInstrumentation,
  uninstallErrorInstrumentation,
  captureError,
  createErrorBoundaryHandler,
  isErrorInstrumentationInstalled,
  parseStackTrace,
  serializeStackFrames,
  cleanFilePath,
  getSourceMapUrl,
  extractSourceMapComment,
  isApplicationFrame,
  getTopApplicationFrames,
  createErrorFingerprint,
  type StackFrame,
  type ParsedStackTrace,
} from './errors';

// Performance instrumentation
export {
  installWebVitalsInstrumentation,
  uninstallWebVitalsInstrumentation,
  measureWebVital,
  getWebVitalThresholds,
  calculateRating,
  isWebVitalsInstalled,
  installPageLoadInstrumentation,
  uninstallPageLoadInstrumentation,
  captureInitialPageLoad,
  getPageLoadTimingData,
  isPageLoadInstalled,
  installSPANavigationInstrumentation,
  uninstallSPANavigationInstrumentation,
  trackNavigation,
  getCurrentTrackedRoute,
  isSPANavigationInstalled,
  installLongTasksInstrumentation,
  uninstallLongTasksInstrumentation,
  reportLongTask,
  measureTask,
  isLongTasksInstalled,
} from './performance';

// Network instrumentation
export {
  installFetchInstrumentation,
  uninstallFetchInstrumentation,
  isFetchInstrumentationInstalled,
  installXHRInstrumentation,
  uninstallXHRInstrumentation,
  isXHRInstrumentationInstalled,
  initializeRetryTracker,
  trackRetryAttempt,
  markRequestSuccess,
  getRetryCount,
  getRetryStates,
  clearRetryStates,
  cleanupStaleRetryStates,
  createRetryFetch,
} from './network';

// User behavior instrumentation
export {
  installClickTracking,
  uninstallClickTracking,
  trackClick,
  isClickTrackingInstalled,
  installRageClickDetection,
  uninstallRageClickDetection,
  reportRageClick,
  isRageClickDetectionInstalled,
  getClickHistory,
  clearClickHistory,
  installNavigationTracking,
  uninstallNavigationTracking,
  trackPageNavigation,
  getTimeOnCurrentPage,
  isNavigationTrackingInstalled,
  installSessionManager,
  uninstallSessionManager,
  startNewSession,
  incrementPageViews,
  incrementInteractions,
  incrementErrors,
  getCurrentSession,
  getSessionId,
  isSessionManagerInstalled,
} from './user-behavior';
