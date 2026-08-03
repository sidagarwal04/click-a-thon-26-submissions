/**
 * Payload hashing utilities
 *
 * Provides utilities for hashing arbitrary payloads (objects, arrays, etc.)
 *
 * @module hash/hash-payload
 */

import { simpleHash } from './simple-hash';

/**
 * Generate a simple hash of a payload (sync)
 *
 * Uses djb2 algorithm after JSON.stringify - fast but not cryptographically secure.
 * Good for idempotency keys where collision resistance is less critical.
 *
 * @param payload - Any JSON-serializable value
 * @returns Hash string (8-character hex)
 *
 * @example
 * ```typescript
 * const hash = hashPayloadSync({ type: 'create', table: 'users', data: { name: 'John' } });
 * // Returns something like '1abc2def'
 * ```
 */
export const hashPayloadSync = (payload: unknown): string => {
  // Use simpleHash for consistency and to avoid code duplication
  return simpleHash(JSON.stringify(payload));
};

/**
 * Generate a SHA-256 hash of a payload (async)
 *
 * Use this when you need cryptographically secure hashing.
 *
 * @param payload - Any JSON-serializable value
 * @returns Promise resolving to hex hash string
 *
 * @example
 * ```typescript
 * const hash = await hashPayloadAsync({ sensitive: 'data' });
 * ```
 */
export const hashPayloadAsync = async (payload: unknown): Promise<string> => {
  const json = JSON.stringify(payload);
  const encoder = new TextEncoder();
  const data = encoder.encode(json);
  const hashBuffer = await crypto.subtle.digest('SHA-256', data);
  const hashArray = Array.from(new Uint8Array(hashBuffer));
  return hashArray.map((b) => b.toString(16).padStart(2, '0')).join('');
};
