/**
 * PII Scrubber
 * @module compliance/pii-scrubber
 */

import { isPlainObject } from '@open-zentra/foundation-data-model';

import type { PIIDetectionResult, PiiFieldType, PIIPattern } from '../types';
import { PII_FIELD_TYPE } from '../types/constants';

/**
 * Built-in PII patterns - single source of truth
 */
export const BUILT_IN_PII_PATTERNS: PIIPattern[] = [
  {
    name: 'email',
    type: PII_FIELD_TYPE.EMAIL,
    pattern: /[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}/g,
    replacement: '[EMAIL_REDACTED]',
    priority: 1,
  },
  {
    name: 'phone_us',
    type: PII_FIELD_TYPE.PHONE,
    pattern: /(\+?1[-.\s]?)?\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}/g,
    replacement: '[PHONE_REDACTED]',
    priority: 5,
  },
  {
    name: 'phone_international',
    type: PII_FIELD_TYPE.PHONE,
    pattern: /\+?[0-9]{1,4}[-.\s]?\(?[0-9]{1,4}\)?[-.\s]?[0-9]{1,4}[-.\s]?[0-9]{1,9}/g,
    replacement: '[PHONE_REDACTED]',
    priority: 6,
  },
  {
    name: 'ssn',
    type: PII_FIELD_TYPE.SSN,
    pattern: /\b\d{3}[-.\s]?\d{2}[-.\s]?\d{4}\b/g,
    replacement: '[SSN_REDACTED]',
    priority: 1,
  },
  {
    name: 'credit_card',
    type: PII_FIELD_TYPE.CREDIT_CARD,
    pattern: /\b(?:\d{4}[-.\s]?){3}\d{4}\b/g,
    replacement: '[CC_REDACTED]',
    priority: 1,
  },
  {
    name: 'ip_address_v4',
    type: PII_FIELD_TYPE.IP_ADDRESS,
    pattern:
      /\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b/g,
    replacement: '[IP_REDACTED]',
    priority: 4,
  },
  {
    name: 'api_key',
    type: PII_FIELD_TYPE.API_KEY,
    pattern: /\b(?:api[_-]?key|apikey|api_secret|secret_key)[\s:=]+['"]?[a-zA-Z0-9_-]{20,}['"]?/gi,
    replacement: '[API_KEY_REDACTED]',
    priority: 1,
  },
  {
    name: 'bearer_token',
    type: PII_FIELD_TYPE.TOKEN,
    pattern: /Bearer\s+[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+/gi,
    replacement: '[TOKEN_REDACTED]',
    priority: 2,
  },
  {
    name: 'jwt_token',
    type: PII_FIELD_TYPE.TOKEN,
    pattern: /eyJ[a-zA-Z0-9_-]*\.eyJ[a-zA-Z0-9_-]*\.[a-zA-Z0-9_-]*/g,
    replacement: '[JWT_REDACTED]',
    priority: 1,
  },
];

/**
 * PII Scrubber configuration
 */
export interface PIIScrubberConfig {
  /** Enable automatic PII detection */
  enabled: boolean;
  /** Custom patterns to add */
  customPatterns?: PIIPattern[];
  /** Field names to always scrub */
  piiFields?: string[];
  /** Patterns to disable */
  disabledPatterns?: string[];
}

/**
 * Clone a PIIPattern, creating a fresh RegExp instance so that
 * the global `lastIndex` state is not shared across scrubber instances.
 */
const clonePattern = (pattern: PIIPattern): PIIPattern => ({
  ...pattern,
  pattern: new RegExp(pattern.pattern.source, pattern.pattern.flags),
});

/**
 * Get active patterns based on configuration.
 *
 * Each call returns **cloned** RegExp objects so that multiple
 * scrubber instances (or concurrent calls within the same instance)
 * never share mutable `lastIndex` state.
 */
const getActivePatterns = (config: PIIScrubberConfig): PIIPattern[] => {
  let patterns = BUILT_IN_PII_PATTERNS.map(clonePattern);

  // Add custom patterns (also cloned to avoid shared state)
  if (config.customPatterns) {
    patterns = [...patterns, ...config.customPatterns.map(clonePattern)];
  }

  // Remove disabled patterns
  if (config.disabledPatterns) {
    patterns = patterns.filter((p) => !config.disabledPatterns!.includes(p.name));
  }

  // Sort by priority (lower = higher priority)
  patterns.sort((a, b) => a.priority - b.priority);

  return patterns;
};

/**
 * Create a PII scrubber
 */
export const createPIIScrubber = (config: PIIScrubberConfig) => {
  const patterns = getActivePatterns(config);

  /**
   * Scrub PII from a string
   */
  const scrubString = (value: string): PIIDetectionResult => {
    if (!config.enabled || !value) {
      return { detected: false, redactedValue: value };
    }

    let result = value;
    let detected = false;
    let detectedType: PiiFieldType | undefined;

    for (const pattern of patterns) {
      // Reset regex lastIndex for global patterns
      pattern.pattern.lastIndex = 0;

      if (pattern.pattern.test(value)) {
        detected = true;
        if (!detectedType) {
          detectedType = pattern.type;
        }

        // Reset again before replace
        pattern.pattern.lastIndex = 0;

        if (typeof pattern.replacement === 'function') {
          result = result.replace(pattern.pattern, pattern.replacement);
        } else {
          result = result.replace(pattern.pattern, pattern.replacement);
        }
      }
    }

    return {
      detected,
      type: detectedType,
      redactedValue: result,
    };
  };

  /**
   * Scrub PII from an object
   */
  const scrubObject = (obj: Record<string, unknown>): Record<string, unknown> => {
    if (!config.enabled) {
      return obj;
    }

    const result: Record<string, unknown> = {};

    for (const [key, value] of Object.entries(obj)) {
      // Check if field name is in PII fields list
      if (config.piiFields?.some((field) => key.toLowerCase().includes(field.toLowerCase()))) {
        result[key] = '[REDACTED]';
        continue;
      }

      if (typeof value === 'string') {
        result[key] = scrubString(value).redactedValue;
      } else if (Array.isArray(value)) {
        result[key] = value.map((item) =>
          typeof item === 'string'
            ? scrubString(item).redactedValue
            : isPlainObject(item)
            ? scrubObject(item)
            : item,
        );
      } else if (isPlainObject(value)) {
        result[key] = scrubObject(value);
      } else {
        result[key] = value;
      }
    }

    return result;
  };

  /**
   * Check if a string contains PII
   */
  const containsPII = (value: string): boolean => {
    if (!config.enabled || !value) {
      return false;
    }

    for (const pattern of patterns) {
      pattern.pattern.lastIndex = 0;
      if (pattern.pattern.test(value)) {
        return true;
      }
    }

    return false;
  };

  /**
   * Detect PII type in a string
   */
  const detectPIIType = (value: string): PiiFieldType | null => {
    if (!config.enabled || !value) {
      return null;
    }

    for (const pattern of patterns) {
      pattern.pattern.lastIndex = 0;
      if (pattern.pattern.test(value)) {
        return pattern.type;
      }
    }

    return null;
  };

  return {
    scrubString,
    scrubObject,
    containsPII,
    detectPIIType,
  };
};

/**
 * Create a simple scrubber with default settings
 */
export const createDefaultScrubber = () => {
  return createPIIScrubber({
    enabled: true,
    piiFields: ['email', 'password', 'ssn', 'creditCard', 'phone', 'apiKey', 'token'],
  });
};

/**
 * Scrub a URL to remove sensitive query parameters
 */
export const scrubUrl = (url: string, sensitiveParams: string[] = []): string => {
  const defaultSensitiveParams = [
    'token',
    'api_key',
    'apikey',
    'password',
    'secret',
    'auth',
    'access_token',
    'refresh_token',
    'code',
  ];

  const allSensitiveParams = [...defaultSensitiveParams, ...sensitiveParams];

  try {
    const parsed = new URL(url, 'http://localhost');

    for (const param of allSensitiveParams) {
      if (parsed.searchParams.has(param)) {
        parsed.searchParams.set(param, '[REDACTED]');
      }
    }

    // Also check for PII in remaining params
    const scrubber = createDefaultScrubber();
    for (const [key, value] of parsed.searchParams.entries()) {
      const scrubbed = scrubber.scrubString(value);
      if (scrubbed.detected) {
        parsed.searchParams.set(key, scrubbed.redactedValue);
      }
    }

    return parsed
      .toString()
      .replace('http://localhost', '')
      .replaceAll('%5BREDACTED%5D', '[REDACTED]');
  } catch {
    return url;
  }
};

/**
 * Scrub headers
 */
export const scrubHeaders = (headers: Record<string, string>): Record<string, string> => {
  const sensitiveHeaders = [
    'authorization',
    'x-api-key',
    'x-auth-token',
    'cookie',
    'set-cookie',
    'x-csrf-token',
  ];

  const result: Record<string, string> = {};

  for (const [key, value] of Object.entries(headers)) {
    const lowerKey = key.toLowerCase();
    if (sensitiveHeaders.includes(lowerKey)) {
      result[key] = '[REDACTED]';
    } else {
      result[key] = value;
    }
  }

  return result;
};
