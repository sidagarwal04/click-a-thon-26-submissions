/**
 * Browser utilities
 * @module browser
 */

export { isBrowser } from './is-browser';
export { detectBrowser, detectBrowserAsync, type BrowserInfo } from './detect-browser';
export {
  DETECTION_METHOD,
  DEVICE_TYPE,
  EFFECTIVE_CONNECTION_TYPE,
  type DetectionMethod,
  type DeviceType,
  type EffectiveConnectionType,
} from './types';
