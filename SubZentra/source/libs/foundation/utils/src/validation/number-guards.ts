/**
 * Number type guard utilities
 *
 * Provides type-safe validation functions for numeric values.
 *
 * @module validation/number-guards
 */

/**
 * Check if value is a positive integer (> 0)
 *
 * @param value - Value to check
 * @returns True if value is a positive integer
 *
 * @example
 * ```typescript
 * isPositiveInteger(1);   // true
 * isPositiveInteger(0);   // false
 * isPositiveInteger(-1);  // false
 * isPositiveInteger(1.5); // false
 * isPositiveInteger('1'); // false
 * ```
 */
export const isPositiveInteger = (value: unknown): value is number => {
  return typeof value === 'number' && Number.isInteger(value) && value > 0;
};

/**
 * Check if value is a non-negative number (>= 0)
 *
 * @param value - Value to check
 * @returns True if value is a non-negative number
 *
 * @example
 * ```typescript
 * isNonNegative(0);    // true
 * isNonNegative(1);    // true
 * isNonNegative(1.5);  // true
 * isNonNegative(-1);   // false
 * isNonNegative('1');  // false
 * ```
 */
export const isNonNegative = (value: unknown): value is number => {
  return typeof value === 'number' && value >= 0;
};

/**
 * Check if value is a non-negative integer (>= 0 and integer)
 *
 * @param value - Value to check
 * @returns True if value is a non-negative integer
 */
export const isNonNegativeInteger = (value: unknown): value is number => {
  return typeof value === 'number' && Number.isInteger(value) && value >= 0;
};

/**
 * Check if value is a finite number (not NaN, Infinity, or -Infinity)
 *
 * @param value - Value to check
 * @returns True if value is a finite number
 */
export const isFiniteNumber = (value: unknown): value is number => {
  return typeof value === 'number' && Number.isFinite(value);
};

/**
 * Check if value is within a numeric range (inclusive)
 *
 * @param value - Value to check
 * @param min - Minimum value
 * @param max - Maximum value
 * @returns True if value is within [min, max]
 */
export const isInRange = (value: unknown, min: number, max: number): value is number => {
  return typeof value === 'number' && value >= min && value <= max;
};

/**
 * Check if value is a valid percentage (0-100)
 *
 * @param value - Value to check
 * @returns True if value is between 0 and 100
 */
export const isValidPercentage = (value: unknown): value is number => {
  return isInRange(value, 0, 100);
};

/**
 * Check if value is a valid port number (1-65535)
 *
 * @param value - Value to check
 * @returns True if value is a valid port number
 */
export const isValidPort = (value: unknown): value is number => {
  return isPositiveInteger(value) && value <= 65535;
};
