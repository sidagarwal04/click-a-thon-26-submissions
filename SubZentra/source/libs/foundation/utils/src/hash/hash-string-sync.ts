/**
 * Synchronous hash function
 * @module hash/hash-string-sync
 */

import { simpleHash } from './simple-hash';

/**
 * Synchronous hash function using djb2 algorithm
 * Less secure than SHA-256, use for non-critical purposes only
 * @param value - String to hash
 * @param salt - Optional salt to prepend
 * @returns Hashed string (hex)
 */
export const hashStringSync = (value: string, salt = ''): string => simpleHash(salt + value);
