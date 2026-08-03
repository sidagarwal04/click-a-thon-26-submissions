/**
 * Detect browser information from user agent
 * @module browser/detect-browser
 */

import { isBrowser } from './is-browser';
import {
  DETECTION_METHOD,
  DEVICE_TYPE,
  type DetectionMethod,
  type DeviceType,
  type EffectiveConnectionType,
} from './types';

/**
 * Browser information interface
 */
export interface BrowserInfo {
  name: string;
  version: string;
  os: string;
  osVersion: string;
  deviceType: DeviceType;
  screenWidth: number;
  screenHeight: number;
  viewportWidth: number;
  viewportHeight: number;
  devicePixelRatio: number;
  userAgent: string;
  language: string;
  platform: string;
  hardwareConcurrency: number;
  deviceMemory?: number;
  connectionType?: string;
  effectiveConnectionType?: EffectiveConnectionType;
  touchSupport: boolean;
  /** Method used to detect browser information */
  detectionMethod: DetectionMethod;
  /** CPU architecture (from Client Hints or platform) */
  architecture?: string;
  /** Device model (from Client Hints high-entropy values) */
  model?: string;
  /** Whether the browser is mobile (from Client Hints) */
  mobile?: boolean;
  /** Platform version from Client Hints */
  platformVersion?: string;
}

/**
 * NavigatorUAData interface for Client Hints API
 */
interface NavigatorUABrandVersion {
  brand: string;
  version: string;
}

interface NavigatorUAData {
  brands: NavigatorUABrandVersion[];
  mobile: boolean;
  platform: string;
  getHighEntropyValues(hints: string[]): Promise<HighEntropyValues>;
}

interface HighEntropyValues {
  architecture?: string;
  model?: string;
  platformVersion?: string;
  fullVersionList?: NavigatorUABrandVersion[];
}

declare global {
  interface Navigator {
    userAgentData?: NavigatorUAData;
  }
}

/**
 * Check if Client Hints API is available
 */
const hasClientHints = (): boolean =>
  isBrowser() && 'userAgentData' in navigator && navigator.userAgentData !== undefined;

/**
 * Parse browser info from Client Hints brands
 */
const parseBrowserFromClientHints = (
  brands: NavigatorUABrandVersion[],
): { name: string; version: string } => {
  // Priority order for browser detection from brands
  const browserPriority = ['Google Chrome', 'Microsoft Edge', 'Opera', 'Firefox', 'Safari'];

  // Filter out generic brands
  const significantBrands = brands.filter(
    (b) => !b.brand.includes('Not') && b.brand !== 'Chromium',
  );

  // Find the highest priority browser
  for (const browserName of browserPriority) {
    const found = significantBrands.find((b) => b.brand === browserName);
    if (found) {
      return {
        name: found.brand.replace('Google ', '').replace('Microsoft ', ''),
        version: found.version,
      };
    }
  }

  // Fallback to first significant brand or Chromium
  const fallback = significantBrands[0] || brands.find((b) => b.brand === 'Chromium');
  if (fallback) {
    return { name: fallback.brand, version: fallback.version };
  }

  return { name: 'unknown', version: 'unknown' };
};

/**
 * Parse browser name and version from user agent
 */
const parseBrowserFromUA = (ua: string): { name: string; version: string } => {
  const browsers = [
    { name: 'Edge', pattern: /Edg(?:e|A|iOS)?\/(\d+[\d.]*)/ },
    { name: 'Opera', pattern: /(?:OPR|Opera)\/(\d+[\d.]*)/ },
    { name: 'Chrome', pattern: /Chrome\/(\d+[\d.]*)/ },
    { name: 'Safari', pattern: /Version\/(\d+[\d.]*).*Safari/ },
    { name: 'Firefox', pattern: /Firefox\/(\d+[\d.]*)/ },
    { name: 'IE', pattern: /(?:MSIE |rv:)(\d+[\d.]*)/ },
  ];

  for (const browser of browsers) {
    const match = ua.match(browser.pattern);
    if (match) {
      return { name: browser.name, version: match[1] || 'unknown' };
    }
  }

  return { name: 'unknown', version: 'unknown' };
};

/**
 * Parse OS name and version from user agent
 */
const parseOSFromUA = (ua: string): { name: string; version: string } => {
  const osPatterns = [
    { name: 'Windows', pattern: /Windows NT (\d+[\d.]*)/ },
    { name: 'macOS', pattern: /Mac OS X (\d+[._\d]*)/ },
    { name: 'iOS', pattern: /(?:iPhone|iPad|iPod).*OS (\d+[._\d]*)/ },
    { name: 'Android', pattern: /Android (\d+[\d.]*)/ },
    { name: 'Linux', pattern: /Linux/ },
    { name: 'Chrome OS', pattern: /CrOS/ },
  ];

  for (const os of osPatterns) {
    const match = ua.match(os.pattern);
    if (match) {
      const version = match[1]?.replace(/_/g, '.') || 'unknown';
      return { name: os.name, version };
    }
  }

  return { name: 'unknown', version: 'unknown' };
};

/**
 * Detect device type from user agent
 */
const detectDeviceType = (ua: string): DeviceType => {
  const mobilePattern = /Mobile|Android|iPhone|iPod|BlackBerry|IEMobile|Opera Mini/i;
  const tabletPattern = /iPad|Android(?!.*Mobile)|Tablet/i;

  if (tabletPattern.test(ua)) {
    return DEVICE_TYPE.TABLET;
  }
  if (mobilePattern.test(ua)) {
    return DEVICE_TYPE.MOBILE;
  }
  return DEVICE_TYPE.DESKTOP;
};

/**
 * Get screen information
 */
const getScreenInfo = () => ({
  screenWidth: window.screen.width || 0,
  screenHeight: window.screen.height || 0,
  viewportWidth: window.innerWidth || 0,
  viewportHeight: window.innerHeight || 0,
  devicePixelRatio: window.devicePixelRatio || 1,
});

/**
 * Get device memory (if available)
 */
const getDeviceMemory = (): number | undefined => {
  if ('deviceMemory' in navigator) {
    return (navigator as Navigator & { deviceMemory?: number }).deviceMemory;
  }
  return undefined;
};

/**
 * Get connection information
 */
const getConnectionInfo = (): {
  type?: string;
  effectiveType?: EffectiveConnectionType;
} => {
  if ('connection' in navigator) {
    const connection = (
      navigator as Navigator & {
        connection?: {
          type?: string;
          effectiveType?: EffectiveConnectionType;
        };
      }
    ).connection;

    return {
      type: connection?.type,
      effectiveType: connection?.effectiveType,
    };
  }
  return {};
};

/**
 * Detect touch support
 */
const detectTouchSupport = (): boolean => 'ontouchstart' in window || navigator.maxTouchPoints > 0;

/**
 * Create empty browser info for SSR
 */
const createEmptyBrowserInfo = (): BrowserInfo => ({
  name: 'unknown',
  version: 'unknown',
  os: 'unknown',
  osVersion: 'unknown',
  deviceType: DEVICE_TYPE.UNKNOWN,
  screenWidth: 0,
  screenHeight: 0,
  viewportWidth: 0,
  viewportHeight: 0,
  devicePixelRatio: 1,
  userAgent: '',
  language: 'en',
  platform: '',
  hardwareConcurrency: 1,
  touchSupport: false,
  detectionMethod: DETECTION_METHOD.USER_AGENT,
});

/**
 * Detect browser information from user agent (synchronous)
 * Uses Client Hints API when available with user-agent as fallback
 * @returns Browser information object
 */
export const detectBrowser = (): BrowserInfo => {
  if (!isBrowser()) {
    return createEmptyBrowserInfo();
  }

  const ua = navigator.userAgent;
  const platformStr = navigator.platform;
  const language = navigator.language;
  const screenInfo = getScreenInfo();
  const connectionInfo = getConnectionInfo();

  // Try Client Hints first (low-entropy values are synchronous)
  if (hasClientHints()) {
    const uaData = navigator.userAgentData!;
    const browserInfo = parseBrowserFromClientHints(uaData.brands);
    const deviceType = uaData.mobile ? DEVICE_TYPE.MOBILE : DEVICE_TYPE.DESKTOP;

    return {
      name: browserInfo.name,
      version: browserInfo.version,
      os: uaData.platform || parseOSFromUA(ua).name,
      osVersion: parseOSFromUA(ua).version, // Need high-entropy for accurate version
      deviceType,
      screenWidth: screenInfo.screenWidth,
      screenHeight: screenInfo.screenHeight,
      viewportWidth: screenInfo.viewportWidth,
      viewportHeight: screenInfo.viewportHeight,
      devicePixelRatio: screenInfo.devicePixelRatio,
      userAgent: ua,
      language,
      platform: platformStr,
      hardwareConcurrency: navigator.hardwareConcurrency || 1,
      deviceMemory: getDeviceMemory(),
      connectionType: connectionInfo.type,
      effectiveConnectionType: connectionInfo.effectiveType,
      touchSupport: detectTouchSupport(),
      detectionMethod: DETECTION_METHOD.CLIENT_HINTS,
      mobile: uaData.mobile,
    };
  }

  // Fallback to user-agent parsing
  const browserInfo = parseBrowserFromUA(ua);
  const osInfo = parseOSFromUA(ua);
  const deviceType = detectDeviceType(ua);

  return {
    name: browserInfo.name,
    version: browserInfo.version,
    os: osInfo.name,
    osVersion: osInfo.version,
    deviceType,
    screenWidth: screenInfo.screenWidth,
    screenHeight: screenInfo.screenHeight,
    viewportWidth: screenInfo.viewportWidth,
    viewportHeight: screenInfo.viewportHeight,
    devicePixelRatio: screenInfo.devicePixelRatio,
    userAgent: ua,
    language,
    platform: platformStr,
    hardwareConcurrency: navigator.hardwareConcurrency || 1,
    deviceMemory: getDeviceMemory(),
    connectionType: connectionInfo.type,
    effectiveConnectionType: connectionInfo.effectiveType,
    touchSupport: detectTouchSupport(),
    detectionMethod: DETECTION_METHOD.USER_AGENT,
  };
};

/**
 * Detect browser information asynchronously with high-entropy Client Hints
 * Provides more detailed information when available (architecture, model, platform version)
 * @returns Promise resolving to browser information object
 */
export const detectBrowserAsync = async (): Promise<BrowserInfo> => {
  // Start with synchronous detection
  const baseInfo = detectBrowser();

  // If Client Hints not available or already using user-agent, return base info
  if (!hasClientHints() || baseInfo.detectionMethod === DETECTION_METHOD.USER_AGENT) {
    return baseInfo;
  }

  try {
    const uaData = navigator.userAgentData!;
    const highEntropy = await uaData.getHighEntropyValues([
      'architecture',
      'model',
      'platformVersion',
      'fullVersionList',
    ]);

    // Get full version from high-entropy values
    let fullVersion = baseInfo.version;
    if (highEntropy.fullVersionList) {
      const browserFromFullList = parseBrowserFromClientHints(highEntropy.fullVersionList);
      if (browserFromFullList.version !== 'unknown') {
        fullVersion = browserFromFullList.version;
      }
    }

    return {
      ...baseInfo,
      version: fullVersion,
      osVersion: highEntropy.platformVersion || baseInfo.osVersion,
      architecture: highEntropy.architecture,
      model: highEntropy.model,
      platformVersion: highEntropy.platformVersion,
    };
  } catch {
    // If high-entropy request fails (e.g., permission denied), return base info
    return baseInfo;
  }
};
