/**
 * Tests for number guard utilities
 */

import { describe, expect, it } from 'vitest';

import {
  isFiniteNumber,
  isInRange,
  isNonNegative,
  isNonNegativeInteger,
  isPositiveInteger,
  isValidPercentage,
  isValidPort,
} from './number-guards';

describe('isPositiveInteger', () => {
  it('should return true for positive integers', () => {
    expect(isPositiveInteger(1)).toBe(true);
    expect(isPositiveInteger(100)).toBe(true);
    expect(isPositiveInteger(Number.MAX_SAFE_INTEGER)).toBe(true);
  });

  it('should return false for zero', () => {
    expect(isPositiveInteger(0)).toBe(false);
  });

  it('should return false for negative numbers', () => {
    expect(isPositiveInteger(-1)).toBe(false);
    expect(isPositiveInteger(-100)).toBe(false);
  });

  it('should return false for non-integers', () => {
    expect(isPositiveInteger(1.5)).toBe(false);
    expect(isPositiveInteger(0.1)).toBe(false);
  });

  it('should return false for non-numbers', () => {
    expect(isPositiveInteger('1')).toBe(false);
    expect(isPositiveInteger(null)).toBe(false);
    expect(isPositiveInteger(undefined)).toBe(false);
    expect(isPositiveInteger(NaN)).toBe(false);
    expect(isPositiveInteger(Infinity)).toBe(false);
  });
});

describe('isNonNegative', () => {
  it('should return true for zero', () => {
    expect(isNonNegative(0)).toBe(true);
  });

  it('should return true for positive numbers', () => {
    expect(isNonNegative(1)).toBe(true);
    expect(isNonNegative(1.5)).toBe(true);
    expect(isNonNegative(100)).toBe(true);
  });

  it('should return false for negative numbers', () => {
    expect(isNonNegative(-1)).toBe(false);
    expect(isNonNegative(-0.1)).toBe(false);
  });

  it('should return false for non-numbers', () => {
    expect(isNonNegative('0')).toBe(false);
    expect(isNonNegative(null)).toBe(false);
    expect(isNonNegative(NaN)).toBe(false);
  });
});

describe('isNonNegativeInteger', () => {
  it('should return true for zero', () => {
    expect(isNonNegativeInteger(0)).toBe(true);
  });

  it('should return true for positive integers', () => {
    expect(isNonNegativeInteger(1)).toBe(true);
    expect(isNonNegativeInteger(100)).toBe(true);
  });

  it('should return false for non-integers', () => {
    expect(isNonNegativeInteger(0.5)).toBe(false);
    expect(isNonNegativeInteger(1.5)).toBe(false);
  });

  it('should return false for negative numbers', () => {
    expect(isNonNegativeInteger(-1)).toBe(false);
  });
});

describe('isFiniteNumber', () => {
  it('should return true for finite numbers', () => {
    expect(isFiniteNumber(0)).toBe(true);
    expect(isFiniteNumber(1)).toBe(true);
    expect(isFiniteNumber(-1)).toBe(true);
    expect(isFiniteNumber(1.5)).toBe(true);
  });

  it('should return false for Infinity', () => {
    expect(isFiniteNumber(Infinity)).toBe(false);
    expect(isFiniteNumber(-Infinity)).toBe(false);
  });

  it('should return false for NaN', () => {
    expect(isFiniteNumber(NaN)).toBe(false);
  });

  it('should return false for non-numbers', () => {
    expect(isFiniteNumber('1')).toBe(false);
    expect(isFiniteNumber(null)).toBe(false);
  });
});

describe('isInRange', () => {
  it('should return true for values within range', () => {
    expect(isInRange(5, 0, 10)).toBe(true);
    expect(isInRange(0, 0, 10)).toBe(true);
    expect(isInRange(10, 0, 10)).toBe(true);
  });

  it('should return false for values outside range', () => {
    expect(isInRange(-1, 0, 10)).toBe(false);
    expect(isInRange(11, 0, 10)).toBe(false);
  });

  it('should handle negative ranges', () => {
    expect(isInRange(-5, -10, 0)).toBe(true);
    expect(isInRange(-11, -10, 0)).toBe(false);
  });

  it('should return false for non-numbers', () => {
    expect(isInRange('5', 0, 10)).toBe(false);
  });
});

describe('isValidPercentage', () => {
  it('should return true for valid percentages', () => {
    expect(isValidPercentage(0)).toBe(true);
    expect(isValidPercentage(50)).toBe(true);
    expect(isValidPercentage(100)).toBe(true);
    expect(isValidPercentage(33.33)).toBe(true);
  });

  it('should return false for invalid percentages', () => {
    expect(isValidPercentage(-1)).toBe(false);
    expect(isValidPercentage(101)).toBe(false);
  });
});

describe('isValidPort', () => {
  it('should return true for valid ports', () => {
    expect(isValidPort(1)).toBe(true);
    expect(isValidPort(80)).toBe(true);
    expect(isValidPort(443)).toBe(true);
    expect(isValidPort(3000)).toBe(true);
    expect(isValidPort(65535)).toBe(true);
  });

  it('should return false for invalid ports', () => {
    expect(isValidPort(0)).toBe(false);
    expect(isValidPort(-1)).toBe(false);
    expect(isValidPort(65536)).toBe(false);
    expect(isValidPort(1.5)).toBe(false);
    expect(isValidPort('80')).toBe(false);
  });
});
