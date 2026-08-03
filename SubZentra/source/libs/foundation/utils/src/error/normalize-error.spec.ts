/**
 * Tests for error normalization utilities
 */

import { describe, expect, it } from 'vitest';

import {
  formatErrorMessage,
  getErrorMessage,
  getErrorName,
  normalizeError,
} from './normalize-error';

describe('normalizeError', () => {
  it('should return Error instances unchanged', () => {
    const error = new Error('test');
    const result = normalizeError(error);

    expect(result).toBe(error);
    expect(result.message).toBe('test');
  });

  it('should convert string to Error', () => {
    const result = normalizeError('string error');

    expect(result).toBeInstanceOf(Error);
    expect(result.message).toBe('string error');
  });

  it('should convert object with message to Error', () => {
    const result = normalizeError({ message: 'object error', code: 500 });

    expect(result).toBeInstanceOf(Error);
    expect(result.message).toBe('object error');
  });

  it('should preserve name from error-like objects', () => {
    const result = normalizeError({
      message: 'custom error',
      name: 'CustomError',
    });

    expect(result.message).toBe('custom error');
    expect(result.name).toBe('CustomError');
  });

  it('should convert numbers to Error', () => {
    const result = normalizeError(404);

    expect(result).toBeInstanceOf(Error);
    expect(result.message).toBe('404');
  });

  it('should convert null to Error', () => {
    const result = normalizeError(null);

    expect(result).toBeInstanceOf(Error);
    expect(result.message).toBe('null');
  });

  it('should convert undefined to Error', () => {
    const result = normalizeError(undefined);

    expect(result).toBeInstanceOf(Error);
    expect(result.message).toBe('undefined');
  });

  it('should handle TypeError correctly', () => {
    const error = new TypeError('type error');
    const result = normalizeError(error);

    expect(result).toBe(error);
    expect(result.name).toBe('TypeError');
  });
});

describe('formatErrorMessage', () => {
  it('should format message with context', () => {
    const result = formatErrorMessage('MyComponent', 'Something went wrong');

    expect(result).toBe('[MyComponent] Something went wrong');
  });

  it('should handle empty context', () => {
    const result = formatErrorMessage('', 'Error');

    expect(result).toBe('[] Error');
  });
});

describe('getErrorMessage', () => {
  it('should extract message from Error', () => {
    const error = new Error('test message');
    expect(getErrorMessage(error)).toBe('test message');
  });

  it('should return string as-is', () => {
    expect(getErrorMessage('string error')).toBe('string error');
  });

  it('should extract message from object', () => {
    expect(getErrorMessage({ message: 'object message' })).toBe('object message');
  });

  it('should convert other values to string', () => {
    expect(getErrorMessage(123)).toBe('123');
    expect(getErrorMessage(null)).toBe('null');
  });
});

describe('getErrorName', () => {
  it('should return name from Error', () => {
    const error = new Error('test');
    expect(getErrorName(error)).toBe('Error');
  });

  it('should return name from TypeError', () => {
    const error = new TypeError('type error');
    expect(getErrorName(error)).toBe('TypeError');
  });

  it('should return name from object', () => {
    expect(getErrorName({ name: 'CustomError', message: 'test' })).toBe('CustomError');
  });

  it('should return default for unknown types', () => {
    expect(getErrorName('string')).toBe('Error');
    expect(getErrorName(123)).toBe('Error');
    expect(getErrorName(null)).toBe('Error');
  });
});
