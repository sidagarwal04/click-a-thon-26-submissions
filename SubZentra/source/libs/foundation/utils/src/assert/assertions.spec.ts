/**
 * Tests for assertion utilities
 */

import { describe, expect, it } from 'vitest';

import {
  assert,
  assertDefined,
  assertInRange,
  assertNever,
  assertNonEmpty,
  assertNotNull,
  assertType,
} from './assertions';

describe('assert', () => {
  it('should not throw for truthy conditions', () => {
    expect(() => assert(true, 'should not fail')).not.toThrow();
    expect(() => assert(1, 'should not fail')).not.toThrow();
    expect(() => assert('string', 'should not fail')).not.toThrow();
    expect(() => assert({}, 'should not fail')).not.toThrow();
    expect(() => assert([], 'should not fail')).not.toThrow();
  });

  it('should throw for falsy conditions', () => {
    expect(() => assert(false, 'test message')).toThrow('Assertion failed: test message');
    expect(() => assert(0, 'test message')).toThrow('Assertion failed: test message');
    expect(() => assert('', 'test message')).toThrow('Assertion failed: test message');
    expect(() => assert(null, 'test message')).toThrow('Assertion failed: test message');
    expect(() => assert(undefined, 'test message')).toThrow('Assertion failed: test message');
  });
});

describe('assertDefined', () => {
  it('should return value if defined', () => {
    expect(assertDefined('hello', 'value')).toBe('hello');
    expect(assertDefined(0, 'value')).toBe(0);
    expect(assertDefined(false, 'value')).toBe(false);
    expect(assertDefined('', 'value')).toBe('');
  });

  it('should throw for null', () => {
    expect(() => assertDefined(null, 'testValue')).toThrow('testValue is required but was null');
  });

  it('should throw for undefined', () => {
    expect(() => assertDefined(undefined, 'testValue')).toThrow(
      'testValue is required but was undefined',
    );
  });
});

describe('assertNotNull', () => {
  it('should return value if not null', () => {
    expect(assertNotNull('hello', 'value')).toBe('hello');
    expect(assertNotNull(undefined, 'value')).toBe(undefined);
    expect(assertNotNull(0, 'value')).toBe(0);
  });

  it('should throw for null', () => {
    expect(() => assertNotNull(null, 'testValue')).toThrow('testValue must not be null');
  });
});

describe('assertType', () => {
  const isString = (v: unknown): v is string => typeof v === 'string';
  const isNumber = (v: unknown): v is number => typeof v === 'number';

  it('should return value if type guard passes', () => {
    expect(assertType('hello', isString, 'string')).toBe('hello');
    expect(assertType(42, isNumber, 'number')).toBe(42);
  });

  it('should throw if type guard fails', () => {
    expect(() => assertType(123, isString, 'string')).toThrow('Expected string but got number');
    expect(() => assertType('hello', isNumber, 'number')).toThrow('Expected number but got string');
  });
});

describe('assertNever', () => {
  it('should throw with default message', () => {
    const value = 'unexpected' as never;
    expect(() => assertNever(value)).toThrow('Unexpected value: "unexpected"');
  });

  it('should throw with custom message', () => {
    const value = 42 as never;
    expect(() => assertNever(value, 'Custom error')).toThrow('Custom error');
  });
});

describe('assertNonEmpty', () => {
  it('should return array if not empty', () => {
    expect(assertNonEmpty([1, 2, 3], 'array')).toEqual([1, 2, 3]);
    expect(assertNonEmpty(['a'], 'array')).toEqual(['a']);
  });

  it('should throw for empty array', () => {
    expect(() => assertNonEmpty([], 'testArray')).toThrow('testArray must not be empty');
  });
});

describe('assertInRange', () => {
  it('should return value if within range', () => {
    expect(assertInRange(5, 0, 10, 'value')).toBe(5);
    expect(assertInRange(0, 0, 10, 'value')).toBe(0);
    expect(assertInRange(10, 0, 10, 'value')).toBe(10);
    expect(assertInRange(-5, -10, 0, 'value')).toBe(-5);
  });

  it('should throw if below minimum', () => {
    expect(() => assertInRange(-1, 0, 10, 'testValue')).toThrow(
      'testValue must be between 0 and 10, got -1',
    );
  });

  it('should throw if above maximum', () => {
    expect(() => assertInRange(11, 0, 10, 'testValue')).toThrow(
      'testValue must be between 0 and 10, got 11',
    );
  });
});
