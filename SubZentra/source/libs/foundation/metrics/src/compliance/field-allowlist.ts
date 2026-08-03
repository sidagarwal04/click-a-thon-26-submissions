/**
 * Field Allowlist/Denylist
 * @module compliance/field-allowlist
 */

import { isPlainObject } from '@open-zentra/foundation-data-model';

import type { FieldListConfig } from '../types';

/**
 * Default denied fields (always scrubbed)
 */
const DEFAULT_DENIED_FIELDS = [
  'password',
  'passwd',
  'secret',
  'apiKey',
  'api_key',
  'apiSecret',
  'api_secret',
  'token',
  'accessToken',
  'access_token',
  'refreshToken',
  'refresh_token',
  'privateKey',
  'private_key',
  'creditCard',
  'credit_card',
  'cardNumber',
  'card_number',
  'cvv',
  'cvc',
  'ssn',
  'socialSecurity',
  'social_security',
];

/**
 * Create a field filter
 */
export const createFieldFilter = (config: Partial<FieldListConfig> = {}) => {
  const {
    allowedFields = [],
    deniedFields = DEFAULT_DENIED_FIELDS,
    allowByDefault = false,
  } = config;

  // Normalize field names to lowercase for comparison
  const normalizedAllowed = new Set(allowedFields.map((f) => f.toLowerCase()));
  const normalizedDenied = new Set(deniedFields.map((f) => f.toLowerCase()));

  /**
   * Check if a field is allowed
   */
  const isFieldAllowed = (fieldName: string): boolean => {
    const normalizedField = fieldName.toLowerCase();

    // Denied fields always take precedence
    if (normalizedDenied.has(normalizedField)) {
      return false;
    }

    // Check if field matches any denied pattern
    for (const denied of normalizedDenied) {
      if (normalizedField.includes(denied)) {
        return false;
      }
    }

    // If we have an allowlist, field must be in it
    if (normalizedAllowed.size > 0) {
      return normalizedAllowed.has(normalizedField);
    }

    // Otherwise use default behavior
    return allowByDefault;
  };

  /**
   * Filter an object to only include allowed fields
   */
  const filterObject = (obj: Record<string, unknown>): Record<string, unknown> => {
    const result: Record<string, unknown> = {};

    for (const [key, value] of Object.entries(obj)) {
      if (isFieldAllowed(key)) {
        if (isPlainObject(value)) {
          result[key] = filterObject(value);
        } else {
          result[key] = value;
        }
      }
    }

    return result;
  };

  /**
   * Redact denied fields in an object
   */
  const redactDeniedFields = (obj: Record<string, unknown>): Record<string, unknown> => {
    const result: Record<string, unknown> = {};

    for (const [key, value] of Object.entries(obj)) {
      if (!isFieldAllowed(key)) {
        result[key] = '[REDACTED]';
      } else if (isPlainObject(value)) {
        result[key] = redactDeniedFields(value);
      } else {
        result[key] = value;
      }
    }

    return result;
  };

  /**
   * Get list of denied fields found in an object
   */
  const findDeniedFields = (obj: Record<string, unknown>, prefix = ''): string[] => {
    const found: string[] = [];

    for (const [key, value] of Object.entries(obj)) {
      const fullKey = prefix ? `${prefix}.${key}` : key;

      if (!isFieldAllowed(key)) {
        found.push(fullKey);
      }

      if (isPlainObject(value)) {
        found.push(...findDeniedFields(value, fullKey));
      }
    }

    return found;
  };

  return {
    isFieldAllowed,
    filterObject,
    redactDeniedFields,
    findDeniedFields,
  };
};

/**
 * Create a span attributes filter
 */
export const createAttributesFilter = (allowedAttributes: string[]) => {
  const filter = createFieldFilter({
    allowedFields: allowedAttributes,
    deniedFields: DEFAULT_DENIED_FIELDS,
    allowByDefault: false,
  });

  /**
   * Filter span attributes
   */
  const filterAttributes = (
    attributes: Record<string, string | number | boolean | undefined>,
  ): Record<string, string | number | boolean | undefined> => {
    const result: Record<string, string | number | boolean | undefined> = {};

    for (const [key, value] of Object.entries(attributes)) {
      if (filter.isFieldAllowed(key)) {
        result[key] = value;
      }
    }

    return result;
  };

  return {
    filterAttributes,
    isAllowed: filter.isFieldAllowed,
  };
};

/**
 * Merge field list configs
 */
export const mergeFieldListConfigs = (
  base: Partial<FieldListConfig>,
  override: Partial<FieldListConfig>,
): FieldListConfig => {
  return {
    allowedFields: [...(base.allowedFields || []), ...(override.allowedFields || [])],
    deniedFields: [
      ...new Set([
        ...(base.deniedFields || DEFAULT_DENIED_FIELDS),
        ...(override.deniedFields || []),
      ]),
    ],
    allowByDefault: override.allowByDefault ?? base.allowByDefault ?? false,
  };
};
