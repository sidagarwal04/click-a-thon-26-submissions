/**
 * Tests for bridge validation utilities
 */

import { describe, expect, it } from 'vitest';

import {
  Milliseconds,
  type ValidationResultData,
} from '@open-zentra/foundation-data-model';
import {
  assert,
  assertDefined,
  deepFreeze,
  isNonNegative,
  isPositiveInteger,
} from '@open-zentra/foundation-utils';

import { resolvePoolConfig, validatePoolConfig, validateRouterConfig } from './validation';

const getMessages = (result: ValidationResultData): string[] =>
  result.issues.map((issue) => issue.message);

describe('validatePoolConfig', () => {
  it('should pass for empty config (uses defaults)', () => {
    const result = validatePoolConfig({});

    expect(result.valid).toBe(true);
    expect(getMessages(result)).toHaveLength(0);
  });

  it('should pass for valid workerCount', () => {
    const result = validatePoolConfig({ workerCount: 4 });

    expect(result.valid).toBe(true);
    expect(getMessages(result)).toHaveLength(0);
  });

  it('should fail for workerCount < 1', () => {
    const result = validatePoolConfig({ workerCount: 0 });

    expect(result.valid).toBe(false);
    expect(getMessages(result)).toContain('workerCount must be a positive integer');
  });

  it('should fail for non-integer workerCount', () => {
    const result = validatePoolConfig({ workerCount: 2.5 });

    expect(result.valid).toBe(false);
    expect(getMessages(result)).toContain('workerCount must be a positive integer');
  });

  it('should warn for workerCount > 16', () => {
    const result = validatePoolConfig({ workerCount: 20 });

    expect(result.valid).toBe(false);
    expect(getMessages(result)).toContain(
      'workerCount should not exceed 16 (diminishing returns with more workers)',
    );
  });

  it('should pass for valid maxQueuePerWorker', () => {
    const result = validatePoolConfig({ maxQueuePerWorker: 20 });

    expect(result.valid).toBe(true);
  });

  it('should fail for maxQueuePerWorker < 1', () => {
    const result = validatePoolConfig({ maxQueuePerWorker: 0 });

    expect(result.valid).toBe(false);
    expect(getMessages(result)).toContain('maxQueuePerWorker must be a positive integer');
  });

  it('should warn for maxQueuePerWorker > 100', () => {
    const result = validatePoolConfig({ maxQueuePerWorker: 150 });

    expect(result.valid).toBe(false);
    expect(getMessages(result)).toContain('maxQueuePerWorker should not exceed 100');
  });

  it('should fail for negative defaultQueryTimeout', () => {
    const result = validatePoolConfig({ defaultQueryTimeout: Milliseconds.from(-1) });

    expect(result.valid).toBe(false);
    expect(getMessages(result)).toContain('defaultQueryTimeout must be non-negative');
  });

  it('should warn for defaultQueryTimeout > 300000', () => {
    const result = validatePoolConfig({ defaultQueryTimeout: Milliseconds.from(400000) });

    expect(result.valid).toBe(false);
    expect(getMessages(result)).toContain(
      'defaultQueryTimeout should not exceed 300000ms (5 minutes)',
    );
  });

  it('should fail for workerInitTimeout < 1000', () => {
    const result = validatePoolConfig({ workerInitTimeout: Milliseconds.from(500) });

    expect(result.valid).toBe(false);
    expect(getMessages(result)).toContain('workerInitTimeout should be at least 1000ms');
  });

  it('should warn for workerInitTimeout > 60000', () => {
    const result = validatePoolConfig({ workerInitTimeout: Milliseconds.from(70000) });

    expect(result.valid).toBe(false);
    expect(getMessages(result)).toContain('workerInitTimeout should not exceed 60000ms');
  });

  it('should fail for negative workerIdleTimeout', () => {
    const result = validatePoolConfig({ workerIdleTimeout: Milliseconds.from(-1) });

    expect(result.valid).toBe(false);
    expect(getMessages(result)).toContain('workerIdleTimeout must be non-negative');
  });

  it('should pass for null workerIdleTimeout (disabled)', () => {
    const result = validatePoolConfig({ workerIdleTimeout: null });

    expect(result.valid).toBe(true);
  });

  it('should collect multiple errors', () => {
    const result = validatePoolConfig({
      workerCount: 0,
      maxQueuePerWorker: -1,
      defaultQueryTimeout: Milliseconds.from(-100),
    });

    expect(result.valid).toBe(false);
    expect(result.issues.length).toBeGreaterThanOrEqual(3);
  });
});

describe('validateRouterConfig', () => {
  it('should pass for empty config', () => {
    const result = validateRouterConfig({});

    expect(result.valid).toBe(true);
    expect(getMessages(result)).toHaveLength(0);
  });

  it('should pass for valid forceBridgeType wasm', () => {
    const result = validateRouterConfig({ forceBridgeType: 'wasm' });

    expect(result.valid).toBe(true);
  });

  it('should pass for valid forceBridgeType native', () => {
    const result = validateRouterConfig({ forceBridgeType: 'native' });

    expect(result.valid).toBe(true);
  });

  it('should fail for invalid forceBridgeType', () => {
    const result = validateRouterConfig({ forceBridgeType: 'invalid' as 'wasm' });

    expect(result.valid).toBe(false);
    expect(getMessages(result)).toContain('forceBridgeType must be "wasm" or "native"');
  });

  it('should pass for valid idleTimeout', () => {
    const result = validateRouterConfig({ idleTimeout: 30000 });

    expect(result.valid).toBe(true);
  });

  it('should fail for negative idleTimeout', () => {
    const result = validateRouterConfig({ idleTimeout: -1 });

    expect(result.valid).toBe(false);
    expect(getMessages(result)).toContain('idleTimeout must be non-negative');
  });

  it('should warn for idleTimeout > 1 hour', () => {
    const result = validateRouterConfig({ idleTimeout: 4000000 });

    expect(result.valid).toBe(false);
    expect(getMessages(result)).toContain('idleTimeout should not exceed 3600000ms (1 hour)');
  });
});

describe('deepFreeze', () => {
  it('should freeze an object', () => {
    const obj = { a: 1, b: 2 };
    const frozen = deepFreeze(obj);

    expect(Object.isFrozen(frozen)).toBe(true);
  });

  it('should freeze nested objects', () => {
    const obj = {
      outer: {
        inner: {
          value: 'test',
        },
      },
    };
    const frozen = deepFreeze(obj);

    expect(Object.isFrozen(frozen.outer)).toBe(true);
    expect(Object.isFrozen(frozen.outer.inner)).toBe(true);
  });

  it('should freeze arrays', () => {
    const obj = {
      items: [1, 2, 3],
    };
    const frozen = deepFreeze(obj);

    expect(Object.isFrozen(frozen.items)).toBe(true);
  });

  it('should handle already frozen objects', () => {
    const inner = Object.freeze({ value: 1 });
    const obj = { inner };

    expect(() => deepFreeze(obj)).not.toThrow();
    expect(Object.isFrozen(deepFreeze(obj))).toBe(true);
  });

  it('should return the same reference', () => {
    const obj = { a: 1 };
    const frozen = deepFreeze(obj);

    expect(frozen).toBe(obj);
  });
});

describe('assert', () => {
  it('should not throw for truthy values', () => {
    expect(() => assert(true, 'error')).not.toThrow();
    expect(() => assert(1, 'error')).not.toThrow();
    expect(() => assert('string', 'error')).not.toThrow();
    expect(() => assert({}, 'error')).not.toThrow();
  });

  it('should throw for falsy values', () => {
    expect(() => assert(false, 'test error')).toThrow('Assertion failed: test error');
    expect(() => assert(0, 'test error')).toThrow('Assertion failed: test error');
    expect(() => assert('', 'test error')).toThrow('Assertion failed: test error');
    expect(() => assert(null, 'test error')).toThrow('Assertion failed: test error');
    expect(() => assert(undefined, 'test error')).toThrow('Assertion failed: test error');
  });
});

describe('assertDefined', () => {
  it('should return the value if defined', () => {
    expect(assertDefined('value', 'test')).toBe('value');
    expect(assertDefined(0, 'test')).toBe(0);
    expect(assertDefined(false, 'test')).toBe(false);
  });

  it('should throw for null', () => {
    expect(() => assertDefined(null, 'myValue')).toThrow('myValue is required but was null');
  });

  it('should throw for undefined', () => {
    expect(() => assertDefined(undefined, 'myValue')).toThrow(
      'myValue is required but was undefined',
    );
  });
});

describe('isPositiveInteger', () => {
  it('should return true for positive integers', () => {
    expect(isPositiveInteger(1)).toBe(true);
    expect(isPositiveInteger(100)).toBe(true);
  });

  it('should return false for zero', () => {
    expect(isPositiveInteger(0)).toBe(false);
  });

  it('should return false for negative numbers', () => {
    expect(isPositiveInteger(-1)).toBe(false);
  });

  it('should return false for non-integers', () => {
    expect(isPositiveInteger(1.5)).toBe(false);
    expect(isPositiveInteger('1')).toBe(false);
  });
});

describe('isNonNegative', () => {
  it('should return true for non-negative numbers', () => {
    expect(isNonNegative(0)).toBe(true);
    expect(isNonNegative(1)).toBe(true);
    expect(isNonNegative(1.5)).toBe(true);
  });

  it('should return false for negative numbers', () => {
    expect(isNonNegative(-1)).toBe(false);
    expect(isNonNegative(-0.1)).toBe(false);
  });

  it('should return false for non-numbers', () => {
    expect(isNonNegative('0')).toBe(false);
    expect(isNonNegative(null)).toBe(false);
  });
});

describe('resolvePoolConfig', () => {
  it('should apply defaults for empty config', () => {
    const resolved = resolvePoolConfig({});

    expect(resolved.maxQueuePerWorker).toBe(10);
    expect(resolved.defaultQueryTimeout).toBe(30000);
    expect(resolved.workerInitTimeout).toBe(10000);
    expect(resolved.workerIdleTimeout).toBeNull();
    expect(resolved.enableTableLocking).toBe(true);
    expect(resolved.restartFailedWorkers).toBe(true);
    expect(resolved.debug).toBe(false);
  });

  it('should override defaults with provided values', () => {
    const resolved = resolvePoolConfig({
      workerCount: 2,
      maxQueuePerWorker: 5,
      defaultQueryTimeout: Milliseconds.from(15000),
      debug: true,
    });

    expect(resolved.workerCount).toBe(2);
    expect(resolved.maxQueuePerWorker).toBe(5);
    expect(resolved.defaultQueryTimeout).toBe(15000);
    expect(resolved.debug).toBe(true);
  });

  it('should handle null workerIdleTimeout', () => {
    const resolved = resolvePoolConfig({ workerIdleTimeout: null });

    expect(resolved.workerIdleTimeout).toBeNull();
  });

  it('should handle explicit workerIdleTimeout', () => {
    const resolved = resolvePoolConfig({ workerIdleTimeout: Milliseconds.from(60000) });

    expect(resolved.workerIdleTimeout).toBe(60000);
  });
});
