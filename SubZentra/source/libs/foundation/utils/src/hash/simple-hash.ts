/**
 * Simple hash implementation (djb2 algorithm)
 * @module hash/simple-hash
 * @internal
 */

/**
 * Simple hash implementation using djb2 algorithm
 * Less secure than SHA-256, use for non-critical purposes only
 * @internal
 */
export const simpleHash = (str: string): string => {
  let hash = 5381;
  for (let i = 0; i < str.length; i++) {
    hash = (hash * 33) ^ str.charCodeAt(i);
  }
  return (hash >>> 0).toString(16).padStart(8, '0');
};
