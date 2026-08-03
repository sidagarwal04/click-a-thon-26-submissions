/**
 * Random value generators for testing
 * @module test/random
 */

/**
 * Generates a random string with optional prefix
 *
 * @param prefix - Optional prefix for the string
 * @returns Random string
 */
export function randomString(prefix?: string): string {
  const randomId = Math.floor(Math.random() * 0xffffffff).toString(16);
  return prefix ? `${prefix}-${randomId}` : randomId;
}

/**
 * Generates a random number within a range
 *
 * @param min - Minimum value (inclusive)
 * @param max - Maximum value (exclusive)
 * @returns Random number
 */
export function randomNumber(min = 0, max = 100): number {
  return Math.floor(Math.random() * (max - min)) + min;
}

/**
 * Picks a random element from an array
 *
 * @param arr - Array to pick from
 * @returns Random element
 */
export function randomElement<T>(arr: readonly T[]): T {
  return arr[Math.floor(Math.random() * arr.length)];
}

/**
 * Generates a random boolean
 *
 * @returns Random boolean
 */
export function randomBoolean(): boolean {
  return Math.random() >= 0.5;
}
