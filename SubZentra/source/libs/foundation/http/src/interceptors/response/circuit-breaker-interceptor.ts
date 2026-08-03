/**
 * Circuit Breaker Response Interceptor
 *
 * Tracks consecutive failures per host and short-circuits requests when a
 * host is determined to be unhealthy, preventing thundering-herd retries.
 *
 * @module interceptors/response/circuit-breaker-interceptor
 */

import type { AxiosError, AxiosInstance, AxiosResponse, InternalAxiosRequestConfig } from 'axios';
import { isAxiosError } from 'axios';

import { createDebugLogger } from '@open-zentra/foundation-utils';

import {
  AXIOS_ERROR_CODE,
  DEFAULT_HTTP_CIRCUIT_BREAKER_CONFIG,
  HTTP_STATUS,
} from '../../core/constants';
import { extractHostKey, getRequestMetadata } from '../../core/request-metadata';
import type { HttpCircuitBreakerConfig } from '../../core/types';
import { HttpServerError } from '../../errors/http-errors';

// =============================================================================
// Types
// =============================================================================

/** Circuit breaker configuration */
export type CircuitBreakerConfig = HttpCircuitBreakerConfig;

/** Circuit states */
const CIRCUIT_STATE = {
  CLOSED: 'closed',
  OPEN: 'open',
  HALF_OPEN: 'half_open',
} as const;

type CircuitState = (typeof CIRCUIT_STATE)[keyof typeof CIRCUIT_STATE];

/** Per-host circuit state */
interface HostCircuit {
  state: CircuitState;
  failureCount: number;
  lastFailureTime: number;
  halfOpenRequests: number;
  updatedAt: number;
}

// =============================================================================
// Defaults
// =============================================================================

export const DEFAULT_CIRCUIT_BREAKER_CONFIG: Readonly<CircuitBreakerConfig> =
  DEFAULT_HTTP_CIRCUIT_BREAKER_CONFIG;

// =============================================================================
// Circuit Breaker
// =============================================================================

/**
 * Per-host circuit breaker tracker.
 */
export class CircuitBreaker {
  private readonly circuits = new Map<string, HostCircuit>();
  private readonly config: CircuitBreakerConfig;
  private readonly logger: ReturnType<typeof createDebugLogger>;

  constructor(config: Partial<CircuitBreakerConfig> = {}) {
    this.config = { ...DEFAULT_CIRCUIT_BREAKER_CONFIG, ...config };
    this.logger = createDebugLogger('HttpClient:CircuitBreaker', this.config.debug);
  }

  /**
   * Extract host key from request URL + optional base URL.
   */
  getHostKey(url: string | undefined, baseUrl?: string): string {
    return extractHostKey(url, baseUrl);
  }

  /**
   * Check whether a request to the given host should be allowed.
   */
  allowRequest(host: string): boolean {
    this.pruneCircuits();

    const circuit = this.circuits.get(host);
    if (!circuit) {
      return true;
    }

    this.touchCircuit(circuit);

    switch (circuit.state) {
      case CIRCUIT_STATE.CLOSED:
        return true;

      case CIRCUIT_STATE.OPEN: {
        if (Date.now() - circuit.lastFailureTime >= this.config.resetTimeoutMs) {
          circuit.state = CIRCUIT_STATE.HALF_OPEN;
          circuit.halfOpenRequests = 0;
          this.logger.debug(`Circuit for "${host}" moved to HALF_OPEN`);
          return true;
        }
        return false;
      }

      case CIRCUIT_STATE.HALF_OPEN:
        return circuit.halfOpenRequests < this.config.halfOpenMaxRequests;
    }
  }

  /**
   * Record a successful response.
   */
  recordSuccess(host: string): void {
    this.pruneCircuits();

    const circuit = this.circuits.get(host);
    if (!circuit) {
      return;
    }

    if (circuit.state === CIRCUIT_STATE.HALF_OPEN) {
      this.logger.debug(`Circuit for "${host}" closed after successful probe`);
    }

    circuit.state = CIRCUIT_STATE.CLOSED;
    circuit.failureCount = 0;
    circuit.halfOpenRequests = 0;
    this.touchCircuit(circuit);
  }

  /**
   * Record a failure response.
   */
  recordFailure(host: string): void {
    this.pruneCircuits();

    const circuit = this.getOrCreateCircuit(host);
    circuit.failureCount += 1;
    circuit.lastFailureTime = Date.now();
    this.touchCircuit(circuit);

    if (circuit.state === CIRCUIT_STATE.HALF_OPEN) {
      circuit.state = CIRCUIT_STATE.OPEN;
      this.logger.debug(`Circuit for "${host}" re-opened after failed probe`);
      return;
    }

    if (circuit.failureCount >= this.config.failureThreshold) {
      circuit.state = CIRCUIT_STATE.OPEN;
      this.logger.debug(
        `Circuit for "${host}" opened after ${circuit.failureCount} consecutive failures`,
      );
    }
  }

  /**
   * Increment half-open probe counter.
   */
  recordHalfOpenRequest(host: string): void {
    this.pruneCircuits();

    const circuit = this.circuits.get(host);
    if (circuit?.state === CIRCUIT_STATE.HALF_OPEN) {
      circuit.halfOpenRequests += 1;
      this.touchCircuit(circuit);
    }
  }

  /**
   * Get the current state for a host.
   */
  getState(host: string): CircuitState {
    this.pruneCircuits();
    return this.circuits.get(host)?.state ?? CIRCUIT_STATE.CLOSED;
  }

  /**
   * Reset all circuit state.
   */
  reset(): void {
    this.circuits.clear();
  }

  /**
   * Number of tracked host entries.
   */
  get size(): number {
    this.pruneCircuits();
    return this.circuits.size;
  }

  private getOrCreateCircuit(host: string): HostCircuit {
    const existingCircuit = this.circuits.get(host);
    if (existingCircuit) {
      return existingCircuit;
    }

    const circuit: HostCircuit = {
      state: CIRCUIT_STATE.CLOSED,
      failureCount: 0,
      lastFailureTime: 0,
      halfOpenRequests: 0,
      updatedAt: Date.now(),
    };
    this.circuits.set(host, circuit);
    return circuit;
  }

  private touchCircuit(circuit: HostCircuit): void {
    circuit.updatedAt = Date.now();
  }

  private pruneCircuits(): void {
    const now = Date.now();

    if (this.config.hostTtlMs > 0) {
      for (const [host, circuit] of this.circuits.entries()) {
        if (now - circuit.updatedAt > this.config.hostTtlMs) {
          this.circuits.delete(host);
        }
      }
    }

    if (this.config.maxHosts > 0 && this.circuits.size > this.config.maxHosts) {
      const sortedByUpdatedAt = [...this.circuits.entries()].sort(
        (entryA, entryB) => entryA[1].updatedAt - entryB[1].updatedAt,
      );

      while (this.circuits.size > this.config.maxHosts && sortedByUpdatedAt.length > 0) {
        const oldestEntry = sortedByUpdatedAt.shift();
        if (oldestEntry) {
          this.circuits.delete(oldestEntry[0]);
        }
      }
    }
  }
}

// =============================================================================
// Interceptor
// =============================================================================

const isFailureStatus = (status: number, failureStatusCodes: readonly number[]): boolean =>
  failureStatusCodes.includes(status);

const isNetworkFailure = (error: unknown): error is AxiosError =>
  isAxiosError(error) &&
  (error.code === AXIOS_ERROR_CODE.NETWORK ||
    error.code === AXIOS_ERROR_CODE.TIMEOUT ||
    error.code === AXIOS_ERROR_CODE.TIMEOUT_ALT);

export interface CircuitBreakerInterceptorOptions {
  readonly circuitBreaker: CircuitBreaker;
  readonly config: CircuitBreakerConfig;
}

/**
 * Creates the circuit breaker response interceptor.
 */
export const createCircuitBreakerInterceptor = (options: CircuitBreakerInterceptorOptions) => {
  const { circuitBreaker, config } = options;

  const onFulfilled = (response: AxiosResponse): AxiosResponse => {
    const hostKey =
      response.config.__oiHttpHostKey ??
      circuitBreaker.getHostKey(response.config.url, response.config.baseURL);

    if (isFailureStatus(response.status, config.failureStatusCodes)) {
      circuitBreaker.recordFailure(hostKey);
    } else {
      circuitBreaker.recordSuccess(hostKey);
    }

    return response;
  };

  const onRejected = async (error: unknown): Promise<never> => {
    if (config.countNetworkErrors && isNetworkFailure(error)) {
      const hostKey =
        error.config?.__oiHttpHostKey ??
        circuitBreaker.getHostKey(error.config?.url, error.config?.baseURL);
      circuitBreaker.recordFailure(hostKey);
    }

    throw error;
  };

  return { onFulfilled, onRejected };
};

/**
 * Creates a request interceptor that rejects requests when the circuit
 * for the target host is open.
 */
export const createCircuitBreakerRequestInterceptor = (circuitBreaker: CircuitBreaker) => {
  const onFulfilled = (config: InternalAxiosRequestConfig): InternalAxiosRequestConfig => {
    const requestMetadata = getRequestMetadata(config);
    const hostKey = requestMetadata.hostKey;
    config.__oiHttpHostKey = hostKey;

    if (!circuitBreaker.allowRequest(hostKey)) {
      throw new HttpServerError(
        HTTP_STATUS.SERVICE_UNAVAILABLE,
        `Circuit breaker open for "${hostKey}"`,
        requestMetadata.requestUrl,
        requestMetadata.method,
      );
    }

    if (circuitBreaker.getState(hostKey) === CIRCUIT_STATE.HALF_OPEN) {
      circuitBreaker.recordHalfOpenRequest(hostKey);
    }

    return config;
  };

  return { onFulfilled };
};

/**
 * Registers both request and response circuit-breaker interceptors.
 */
export const setupCircuitBreakerInterceptor = (
  instance: AxiosInstance,
  config: Partial<CircuitBreakerConfig> = {},
): {
  circuitBreaker: CircuitBreaker;
  requestInterceptorId: number;
  responseInterceptorId: number;
} => {
  const resolvedConfig: CircuitBreakerConfig = { ...DEFAULT_CIRCUIT_BREAKER_CONFIG, ...config };
  const circuitBreaker = new CircuitBreaker(resolvedConfig);

  const { onFulfilled: requestFulfilled } = createCircuitBreakerRequestInterceptor(circuitBreaker);
  const requestInterceptorId = instance.interceptors.request.use(requestFulfilled);

  const { onFulfilled, onRejected } = createCircuitBreakerInterceptor({
    circuitBreaker,
    config: resolvedConfig,
  });
  const responseInterceptorId = instance.interceptors.response.use(onFulfilled, onRejected);

  return { circuitBreaker, requestInterceptorId, responseInterceptorId };
};
