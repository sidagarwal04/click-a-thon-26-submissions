/**
 * Tests for deep-freeze utilities
 */

import { describe, expect, it } from 'vitest';

import { deepFreeze, isDeeplyFrozen } from './deep-freeze';

describe('deepFreeze', () => {
  it('should freeze a simple object', () => {
    const obj = { a: 1, b: 2 };
    const frozen = deepFreeze(obj);

    expect(Object.isFrozen(frozen)).toBe(true);
    expect(frozen.a).toBe(1);
  });

  it('should freeze nested objects', () => {
    const obj = {
      level1: {
        level2: {
          value: 'deep',
        },
      },
    };
    const frozen = deepFreeze(obj);

    expect(Object.isFrozen(frozen)).toBe(true);
    expect(Object.isFrozen(frozen.level1)).toBe(true);
    expect(Object.isFrozen(frozen.level1.level2)).toBe(true);
  });

  it('should freeze arrays', () => {
    const obj = {
      items: [1, 2, 3],
      nested: [{ value: 1 }, { value: 2 }],
    };
    const frozen = deepFreeze(obj);

    expect(Object.isFrozen(frozen.items)).toBe(true);
    expect(Object.isFrozen(frozen.nested)).toBe(true);
    expect(Object.isFrozen(frozen.nested[0])).toBe(true);
  });

  it('should handle already frozen objects', () => {
    const inner = Object.freeze({ value: 1 });
    const obj = { inner };

    // Should not throw when encountering already frozen objects
    expect(() => deepFreeze(obj)).not.toThrow();

    const frozen = deepFreeze(obj);
    expect(Object.isFrozen(frozen)).toBe(true);
  });

  it('should return the same reference', () => {
    const obj = { a: 1 };
    const frozen = deepFreeze(obj);

    expect(frozen).toBe(obj);
  });

  it('should prevent modifications in strict mode', () => {
    const obj = deepFreeze({ value: 1 });

    // In strict mode, this would throw
    // In non-strict, it fails silently
    expect(() => {
      'use strict';
      (obj as { value: number }).value = 2;
    }).toThrow();
  });
});

describe('isDeeplyFrozen', () => {
  it('should return true for primitives', () => {
    expect(isDeeplyFrozen(null)).toBe(true);
    expect(isDeeplyFrozen(undefined)).toBe(true);
    expect(isDeeplyFrozen(42)).toBe(true);
    expect(isDeeplyFrozen('string')).toBe(true);
    expect(isDeeplyFrozen(true)).toBe(true);
  });

  it('should return false for unfrozen objects', () => {
    expect(isDeeplyFrozen({ a: 1 })).toBe(false);
    expect(isDeeplyFrozen([1, 2, 3])).toBe(false);
  });

  it('should return false for shallow frozen objects with unfrozen nested', () => {
    const obj = Object.freeze({
      nested: { value: 1 }, // not frozen
    });

    expect(isDeeplyFrozen(obj)).toBe(false);
  });

  it('should return true for deeply frozen objects', () => {
    const obj = deepFreeze({
      level1: {
        level2: {
          value: 'deep',
        },
      },
      array: [{ item: 1 }],
    });

    expect(isDeeplyFrozen(obj)).toBe(true);
  });

  it('should return true for empty frozen objects', () => {
    expect(isDeeplyFrozen(Object.freeze({}))).toBe(true);
    expect(isDeeplyFrozen(Object.freeze([]))).toBe(true);
  });
});
