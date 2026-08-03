/**
 * HTTP Client Types
 *
 * Core type definitions for the foundation-http library.
 *
 * @module core/types
 */

import type { AxiosInstance } from 'axios';

import type {
  AuthTransport,
  AuthTransportAudience,
  AuthTransportRequest,
} from '@open-zentra/foundation-auth';

/**
 * HTTP retry configuration
 *
 * Named HttpRetryConfig to avoid collision with foundation-utils RetryConfig.
 */
export interface HttpRetryConfig {
  /** Whether retry is enabled */
  readonly enabled: boolean;
  /** Maximum number of retry attempts */
  readonly maxRetries: number;
  /** Initial delay in milliseconds */
  readonly initialDelayMs: number;
  /** Maximum delay in milliseconds */
  readonly maxDelayMs: number;
  /** Backoff multiplier for exponential backoff */
  readonly backoffMultiplier: number;
  /** HTTP status codes that should trigger a retry */
  readonly retryableStatusCodes: readonly number[];
  /** Whether to retry on network errors */
  readonly retryOnNetworkError: boolean;
}

/**
 * Circuit-breaker configuration
 */
export interface HttpCircuitBreakerConfig {
  /** Enable circuit breaker protection */
  readonly enabled: boolean;
  /** Number of consecutive failures before the circuit opens */
  readonly failureThreshold: number;
  /** Cooldown before allowing half-open probe requests */
  readonly resetTimeoutMs: number;
  /** Maximum probe requests allowed while half-open */
  readonly halfOpenMaxRequests: number;
  /** HTTP status codes considered as failures */
  readonly failureStatusCodes: readonly number[];
  /** Whether network/timeout errors count as failures */
  readonly countNetworkErrors: boolean;
  /** Maximum tracked hosts before pruning oldest entries */
  readonly maxHosts: number;
  /** Host entry time-to-live in ms before pruning */
  readonly hostTtlMs: number;
  /** Enable circuit-breaker debug logs */
  readonly debug: boolean;
}

/**
 * Authentication configuration for HTTP client
 */
export interface AuthConfig {
  /** Whether auth is enabled */
  readonly enabled: boolean;
  readonly transport?: AuthTransport;
  readonly audience?: AuthTransportAudience;
  /** Function to get the access token */
  readonly getAccessToken?: (request?: AuthTransportRequest) => Promise<string | null>;
  /** Callback when a 401/403 response is received */
  readonly onUnauthorized?: (statusCode: number, url?: string) => void;
  /** Token type for Authorization header (default: 'Bearer') */
  readonly tokenType?: string;
}

/**
 * Client identification headers configuration
 */
export interface ClientHeadersConfig {
  /** Client ID header value */
  readonly clientId?: string;
  /** Client version header value */
  readonly clientVersion?: string;
  /** Platform identifier */
  readonly platform?: string;
  /** Session ID (can be static or dynamic) */
  readonly sessionId?: string | (() => string);
}

/**
 * HTTP client configuration
 */
export interface HttpClientConfig {
  /** Base URL for all requests */
  readonly baseUrl: string;
  /** Request timeout in milliseconds */
  readonly timeout?: number;
  /** Whether to send credentials (cookies) with requests */
  readonly withCredentials?: boolean;
  /** Default headers for all requests */
  readonly defaultHeaders?: Readonly<Record<string, string>>;
  /** Client identification headers */
  readonly clientHeaders?: ClientHeadersConfig;
  /** Retry configuration */
  readonly retry?: Partial<HttpRetryConfig>;
  /** Auth configuration */
  readonly auth?: Partial<AuthConfig>;
  /** Circuit-breaker configuration */
  readonly circuitBreaker?: Partial<HttpCircuitBreakerConfig>;
  /** Enable debug logging */
  readonly debug?: boolean;
}

/**
 * Fully resolved HTTP client configuration with all defaults applied
 */
export interface ResolvedHttpConfig {
  readonly baseUrl: string;
  readonly timeout: number;
  readonly withCredentials: boolean;
  readonly defaultHeaders: Readonly<Record<string, string>>;
  readonly retry: Readonly<HttpRetryConfig>;
  readonly auth: Readonly<AuthConfig>;
  readonly circuitBreaker: Readonly<HttpCircuitBreakerConfig>;
  readonly debug: boolean;
}

/**
 * Public HTTP context value (for app components and useHttp hook)
 */
export interface HttpContextValue {
  /** The configured axios instance (null before initialization) */
  readonly axios: AxiosInstance | null;
  /** Whether the HTTP client is initialized */
  readonly isInitialized: boolean;
  /** Base URL of the HTTP client */
  readonly baseUrl: string;
}

/**
 * Internal HTTP context value (for sibling foundation libraries)
 */
export interface HttpInternals {
  /** The configured axios instance (null before initialization) */
  readonly axios: AxiosInstance | null;
  /** HTTP client configuration */
  readonly config: HttpClientConfig;
  /** Get current access token */
  readonly getAccessToken: (request?: AuthTransportRequest) => Promise<string | null>;
  readonly authTransport?: AuthTransport;
}

/**
 * HttpProvider component props
 */
export interface HttpProviderProps {
  /** HTTP client configuration */
  readonly config: HttpClientConfig;
  /** Child components */
  readonly children: React.ReactNode;
  /** Optional auth internals for token retrieval */
  readonly authInternals?: {
    readonly getAccessToken?: (request?: AuthTransportRequest) => Promise<string | null>;
    readonly transport?: AuthTransport;
  };
}
