/**
 * Circuit Breaker Interceptor Tests
 */

import type { InternalAxiosRequestConfig } from 'axios';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { HTTP_STATUS } from '../../core/constants';
import { HttpServerError } from '../../errors/http-errors';
import {
  CircuitBreaker,
  createCircuitBreakerRequestInterceptor,
  DEFAULT_CIRCUIT_BREAKER_CONFIG,
} from './circuit-breaker-interceptor';

describe('CircuitBreaker', () => {
  let breaker: CircuitBreaker;

  beforeEach(() => {
    breaker = new CircuitBreaker({
      failureThreshold: 3,
      resetTimeoutMs: 1_000,
      hostTtlMs: 60_000,
      maxHosts: 50,
    });
  });

  describe('initial state', () => {
    it('should allow requests for unknown hosts', () => {
      expect(breaker.allowRequest('example.com')).toBe(true);
    });

    it('should report closed state for unknown hosts', () => {
      expect(breaker.getState('example.com')).toBe('closed');
    });
  });

  describe('getHostKey', () => {
    it('should extract host from absolute URL', () => {
      expect(breaker.getHostKey('https://api.example.com/v1/users')).toBe('api.example.com');
    });

    it('should resolve relative URL against base URL', () => {
      expect(breaker.getHostKey('/v1/users', 'https://api.example.com')).toBe('api.example.com');
    });

    it('should return __unknown__ for undefined URL', () => {
      expect(breaker.getHostKey(undefined)).toBe('__unknown__');
    });

    it('should return __unknown__ for relative URL without base', () => {
      expect(breaker.getHostKey('/relative/path')).toBe('__unknown__');
    });
  });

  describe('failure tracking', () => {
    it('should stay closed below threshold', () => {
      breaker.recordFailure('host');
      breaker.recordFailure('host');
      expect(breaker.getState('host')).toBe('closed');
      expect(breaker.allowRequest('host')).toBe(true);
    });

    it('should open circuit at failure threshold', () => {
      for (let i = 0; i < 3; i++) {
        breaker.recordFailure('host');
      }
      expect(breaker.getState('host')).toBe('open');
      expect(breaker.allowRequest('host')).toBe(false);
    });
  });

  describe('OPEN → HALF_OPEN transition', () => {
    beforeEach(() => {
      vi.useFakeTimers();
    });

    afterEach(() => {
      vi.useRealTimers();
    });

    it('should transition to half_open after reset timeout', () => {
      for (let i = 0; i < 3; i++) {
        breaker.recordFailure('host');
      }

      expect(breaker.allowRequest('host')).toBe(false);
      vi.advanceTimersByTime(1_001);
      expect(breaker.allowRequest('host')).toBe(true);
      expect(breaker.getState('host')).toBe('half_open');
    });
  });

  describe('state pruning', () => {
    it('should prune oldest hosts over maxHosts', () => {
      const bounded = new CircuitBreaker({
        failureThreshold: 3,
        maxHosts: 2,
        hostTtlMs: 60_000,
      });

      bounded.recordFailure('host-a');
      bounded.recordFailure('host-b');
      bounded.recordFailure('host-c');

      expect(bounded.size).toBe(2);
      expect(bounded.getState('host-c')).toBe('closed');
    });

    it('should prune stale hosts by TTL', () => {
      vi.useFakeTimers();
      const ttlBounded = new CircuitBreaker({
        hostTtlMs: 10,
        maxHosts: 20,
      });

      ttlBounded.recordFailure('host-a');
      expect(ttlBounded.size).toBe(1);
      vi.advanceTimersByTime(11);

      expect(ttlBounded.size).toBe(0);
      vi.useRealTimers();
    });
  });
});

describe('createCircuitBreakerRequestInterceptor', () => {
  it('should throw HttpServerError when circuit is open', () => {
    const breaker = new CircuitBreaker({ failureThreshold: 1 });
    breaker.recordFailure('api.example.com');

    const { onFulfilled } = createCircuitBreakerRequestInterceptor(breaker);
    const requestConfig = {
      url: '/users',
      baseURL: 'https://api.example.com',
      method: 'get',
      headers: {},
    } as InternalAxiosRequestConfig;

    expect(() => onFulfilled(requestConfig)).toThrow(HttpServerError);

    try {
      onFulfilled(requestConfig);
    } catch (error) {
      expect(error).toBeInstanceOf(HttpServerError);
      const serverError = error as HttpServerError;
      expect(serverError.statusCode).toBe(HTTP_STATUS.SERVICE_UNAVAILABLE);
      expect(serverError.message).toContain('Circuit breaker open');
    }
  });
});

describe('DEFAULT_CIRCUIT_BREAKER_CONFIG', () => {
  it('should expose expected defaults', () => {
    expect(DEFAULT_CIRCUIT_BREAKER_CONFIG.enabled).toBe(false);
    expect(DEFAULT_CIRCUIT_BREAKER_CONFIG.failureThreshold).toBe(5);
    expect(DEFAULT_CIRCUIT_BREAKER_CONFIG.resetTimeoutMs).toBe(30_000);
    expect(DEFAULT_CIRCUIT_BREAKER_CONFIG.halfOpenMaxRequests).toBe(1);
    expect(DEFAULT_CIRCUIT_BREAKER_CONFIG.failureStatusCodes).toEqual([500, 502, 503, 504]);
    expect(DEFAULT_CIRCUIT_BREAKER_CONFIG.countNetworkErrors).toBe(true);
    expect(DEFAULT_CIRCUIT_BREAKER_CONFIG.maxHosts).toBe(250);
    expect(DEFAULT_CIRCUIT_BREAKER_CONFIG.hostTtlMs).toBe(600_000);
    expect(DEFAULT_CIRCUIT_BREAKER_CONFIG.debug).toBe(false);
  });
});
