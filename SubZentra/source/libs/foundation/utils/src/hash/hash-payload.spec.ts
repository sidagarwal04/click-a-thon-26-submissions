/**
 * Tests for payload hashing utilities
 */

import { describe, expect, it } from 'vitest';

import { hashPayloadAsync, hashPayloadSync } from './hash-payload';

describe('hashPayloadSync', () => {
  it('should hash objects consistently', () => {
    const payload = { a: 1, b: 2 };
    const hash1 = hashPayloadSync(payload);
    const hash2 = hashPayloadSync(payload);

    expect(hash1).toBe(hash2);
  });

  it('should produce different hashes for different payloads', () => {
    const hash1 = hashPayloadSync({ a: 1 });
    const hash2 = hashPayloadSync({ a: 2 });

    expect(hash1).not.toBe(hash2);
  });

  it('should hash strings', () => {
    const hash = hashPayloadSync('test string');

    expect(typeof hash).toBe('string');
    expect(hash.length).toBeGreaterThan(0);
  });

  it('should hash arrays', () => {
    const hash = hashPayloadSync([1, 2, 3]);

    expect(typeof hash).toBe('string');
    expect(hash.length).toBeGreaterThan(0);
  });

  it('should hash nested objects', () => {
    const hash = hashPayloadSync({
      nested: {
        deep: {
          value: 'test',
        },
      },
    });

    expect(typeof hash).toBe('string');
    expect(hash.length).toBeGreaterThan(0);
  });

  it('should hash null', () => {
    const hash = hashPayloadSync(null);

    expect(typeof hash).toBe('string');
    expect(hash.length).toBeGreaterThan(0);
  });

  it('should produce base36 output', () => {
    const hash = hashPayloadSync({ test: 'data' });

    // Base36 contains only 0-9 and a-z
    expect(hash).toMatch(/^[0-9a-z]+$/);
  });
});

describe('hashPayloadAsync', () => {
  it('should hash objects consistently', async () => {
    const payload = { a: 1, b: 2 };
    const hash1 = await hashPayloadAsync(payload);
    const hash2 = await hashPayloadAsync(payload);

    expect(hash1).toBe(hash2);
  });

  it('should produce different hashes for different payloads', async () => {
    const hash1 = await hashPayloadAsync({ a: 1 });
    const hash2 = await hashPayloadAsync({ a: 2 });

    expect(hash1).not.toBe(hash2);
  });

  it('should produce 64-character hex string (SHA-256)', async () => {
    const hash = await hashPayloadAsync({ test: 'data' });

    expect(hash.length).toBe(64);
    expect(hash).toMatch(/^[0-9a-f]+$/);
  });
});
