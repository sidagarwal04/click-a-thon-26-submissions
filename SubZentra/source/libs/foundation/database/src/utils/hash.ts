/**
 * Hash Utilities
 *
 * Functions for generating idempotency keys for mutations.
 *
 * NOTE: For generic hash functions (hashPayloadSync, hashPayloadAsync),
 * import directly from @open-zentra/foundation-utils
 *
 * @module utils/hash
 */

import { hashPayloadAsync, hashPayloadSync } from '@open-zentra/foundation-utils';

// =============================================================================
// Idempotency Key Generation
// =============================================================================

export interface IdempotencyKeyOptions {
  tableName: string;
  entityId: string;
  payload: unknown;
  customKey?: string;
}

/**
 * Generate an idempotency key for a mutation
 * If customKey is provided, uses that. Otherwise hashes the payload.
 */
export const generateIdempotencyKey = (options: IdempotencyKeyOptions): string => {
  // If explicitly provided, use it
  if (options.customKey) return options.customKey;

  // Otherwise, hash the payload (NOT timestamp!)
  const payloadHash = hashPayloadSync(options.payload);
  return `${options.tableName}:${options.entityId}:${payloadHash}`;
};

/**
 * Generate an idempotency key with SHA-256 (async version)
 */
export const generateIdempotencyKeyAsync = async (
  options: IdempotencyKeyOptions,
): Promise<string> => {
  // If explicitly provided, use it
  if (options.customKey) return options.customKey;

  // Otherwise, hash the payload with SHA-256
  const payloadHash = await hashPayloadAsync(options.payload);
  // Truncate to reasonable length
  return `${options.tableName}:${options.entityId}:${payloadHash.substring(0, 16)}`;
};
