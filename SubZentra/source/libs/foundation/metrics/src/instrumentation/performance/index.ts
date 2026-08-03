/**
 * Performance Instrumentation Exports
 * @module instrumentation/performance
 */

export {
  installWebVitalsInstrumentation,
  uninstallWebVitalsInstrumentation,
  measureWebVital,
  getWebVitalThresholds,
  calculateRating,
  isWebVitalsInstalled,
} from './web-vitals';

export {
  installPageLoadInstrumentation,
  uninstallPageLoadInstrumentation,
  captureInitialPageLoad,
  getPageLoadTimingData,
  isPageLoadInstalled,
} from './page-load';

export {
  installSPANavigationInstrumentation,
  uninstallSPANavigationInstrumentation,
  trackNavigation,
  getCurrentTrackedRoute,
  isSPANavigationInstalled,
} from './spa-navigation';

export {
  installLongTasksInstrumentation,
  uninstallLongTasksInstrumentation,
  reportLongTask,
  measureTask,
  isLongTasksInstalled,
} from './long-tasks';
