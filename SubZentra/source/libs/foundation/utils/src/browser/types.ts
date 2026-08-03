/**
 * Browser utility types
 * @module browser/types
 */

/**
 * Detection method constant values
 */
export const DETECTION_METHOD = {
  CLIENT_HINTS: 'client-hints',
  USER_AGENT: 'user-agent',
} as const;

/**
 * Detection method type derived from DETECTION_METHOD constants
 */
export type DetectionMethod = (typeof DETECTION_METHOD)[keyof typeof DETECTION_METHOD];

/**
 * Device type constant values
 */
export const DEVICE_TYPE = {
  DESKTOP: 'desktop',
  MOBILE: 'mobile',
  TABLET: 'tablet',
  UNKNOWN: 'unknown',
} as const;

/**
 * Device type derived from DEVICE_TYPE constants
 */
export type DeviceType = (typeof DEVICE_TYPE)[keyof typeof DEVICE_TYPE];

/**
 * Effective connection type constant values
 */
export const EFFECTIVE_CONNECTION_TYPE = {
  FOUR_G: '4g',
  THREE_G: '3g',
  TWO_G: '2g',
  SLOW_TWO_G: 'slow-2g',
} as const;

/**
 * Effective connection type derived from EFFECTIVE_CONNECTION_TYPE constants
 */
export type EffectiveConnectionType =
  (typeof EFFECTIVE_CONNECTION_TYPE)[keyof typeof EFFECTIVE_CONNECTION_TYPE];
