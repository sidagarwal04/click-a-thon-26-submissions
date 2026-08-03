/**
 * User Behavior Instrumentation Exports
 * @module instrumentation/user-behavior
 */

export {
  installClickTracking,
  uninstallClickTracking,
  trackClick,
  isClickTrackingInstalled,
} from './click-tracker';

export {
  installRageClickDetection,
  uninstallRageClickDetection,
  reportRageClick,
  isRageClickDetectionInstalled,
  getClickHistory,
  clearClickHistory,
} from './rage-click-detector';

export {
  installNavigationTracking,
  uninstallNavigationTracking,
  trackPageNavigation,
  getTimeOnCurrentPage,
  getCurrentTrackedRoute,
  isNavigationTrackingInstalled,
} from './navigation-tracker';

export {
  installSessionManager,
  uninstallSessionManager,
  startNewSession,
  incrementPageViews,
  incrementInteractions,
  incrementErrors,
  getCurrentSession,
  getSessionId,
  isSessionManagerInstalled,
} from './session-manager';
