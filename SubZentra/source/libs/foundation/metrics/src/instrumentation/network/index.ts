/**
 * Network Instrumentation Exports
 * @module instrumentation/network
 */

export {
  installFetchInstrumentation,
  uninstallFetchInstrumentation,
  isFetchInstrumentationInstalled,
} from './fetch-instrumentation';

export {
  installXHRInstrumentation,
  uninstallXHRInstrumentation,
  isXHRInstrumentationInstalled,
} from './xhr-instrumentation';

export {
  initializeRetryTracker,
  trackRetryAttempt,
  markRequestSuccess,
  getRetryCount,
  getRetryStates,
  clearRetryStates,
  cleanupStaleRetryStates,
  createRetryFetch,
} from './retry-tracker';
