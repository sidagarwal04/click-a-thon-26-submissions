/**
 * Tests for database hash utilities
 */

import { describe, expect, it } from 'vitest';

import { hashPayloadAsync, hashPayloadSync } from '@open-zentra/foundation-utils';

import { generateIdempotencyKey, generateIdempotencyKeyAsync } from './hash';

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
  });

  it('should hash null', () => {
    const hash = hashPayloadSync(null);

    expect(typeof hash).toBe('string');
  });

  it('should produce deterministic string output', () => {
    const hash = hashPayloadSync({ test: 'data' });

    expect(typeof hash).toBe('string');
    expect(hash.length).toBeGreaterThan(0);
  });
});

describe('hashPayloadAsync (async SHA-256)', () => {
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

describe('generateIdempotencyKey', () => {
  it('should generate key from table, entity, and payload', () => {
    const key = generateIdempotencyKey({
      tableName: 'users',
      entityId: '123',
      payload: { name: 'John' },
    });

    expect(key).toMatch(/^users:123:/);
  });

  it('should use custom key if provided', () => {
    const key = generateIdempotencyKey({
      tableName: 'users',
      entityId: '123',
      payload: { name: 'John' },
      customKey: 'my-custom-key',
    });

    expect(key).toBe('my-custom-key');
  });

  it('should generate consistent keys for same payload', () => {
    const options = {
      tableName: 'users',
      entityId: '123',
      payload: { name: 'John' },
    };

    const key1 = generateIdempotencyKey(options);
    const key2 = generateIdempotencyKey(options);

    expect(key1).toBe(key2);
  });

  it('should generate different keys for different payloads', () => {
    const key1 = generateIdempotencyKey({
      tableName: 'users',
      entityId: '123',
      payload: { name: 'John' },
    });

    const key2 = generateIdempotencyKey({
      tableName: 'users',
      entityId: '123',
      payload: { name: 'Jane' },
    });

    expect(key1).not.toBe(key2);
  });
});

describe('generateIdempotencyKeyAsync', () => {
  it('should generate key with SHA-256 hash', async () => {
    const key = await generateIdempotencyKeyAsync({
      tableName: 'users',
      entityId: '123',
      payload: { name: 'John' },
    });

    expect(key).toMatch(/^users:123:[0-9a-f]{16}$/);
  });

  it('should use custom key if provided', async () => {
    const key = await generateIdempotencyKeyAsync({
      tableName: 'users',
      entityId: '123',
      payload: { name: 'John' },
      customKey: 'my-custom-key',
    });

    expect(key).toBe('my-custom-key');
  });

  it('should truncate hash to 16 characters', async () => {
    const key = await generateIdempotencyKeyAsync({
      tableName: 'users',
      entityId: '123',
      payload: { name: 'John' },
    });

    // Format: tableName:entityId:hash16
    const parts = key.split(':');
    expect(parts[2].length).toBe(16);
  });
});

// Note: hashQueryKey tests are in @open-zentra/foundation-data-model
