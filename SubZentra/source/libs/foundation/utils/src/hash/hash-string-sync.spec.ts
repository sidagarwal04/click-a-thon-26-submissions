import { describe, expect, it } from 'vitest';

import { hashStringSync } from './hash-string-sync';

describe('hashStringSync', () => {
  it('should return a hex string', () => {
    const result = hashStringSync('test');
    expect(result).toMatch(/^[0-9a-f]+$/);
  });

  it('should return consistent hash for same input', () => {
    const result1 = hashStringSync('hello');
    const result2 = hashStringSync('hello');
    expect(result1).toBe(result2);
  });

  it('should return different hashes for different inputs', () => {
    const result1 = hashStringSync('hello');
    const result2 = hashStringSync('world');
    expect(result1).not.toBe(result2);
  });

  it('should apply salt when provided', () => {
    const result1 = hashStringSync('test', 'salt1');
    const result2 = hashStringSync('test', 'salt2');
    expect(result1).not.toBe(result2);
  });

  it('should handle empty string', () => {
    const result = hashStringSync('');
    expect(result).toMatch(/^[0-9a-f]+$/);
  });

  it('should return 8-character hex string', () => {
    const result = hashStringSync('test');
    expect(result.length).toBe(8);
  });
});
