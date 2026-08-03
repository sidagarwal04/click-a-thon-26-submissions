/**
 * Foundation HTTP Library
 *
 * Enterprise-grade HTTP client built on Axios with:
 * - Request/response interceptors
 * - Automatic token injection
 * - Retry with exponential backoff
 * - Typed error handling
 *
 * @module foundation-http
 *
 * @example
 * ```tsx
 * import { HttpProvider, useHttp } from '@open-zentra/foundation-http';
 *
 * const App = () => (
 *   <HttpProvider config={{ baseUrl: 'https://api.example.com' }}>
 *     <YourApp />
 *   </HttpProvider>
 * );
 *
 * const Component = () => {
 *   const { axios, isInitialized } = useHttp();
 *   if (!isInitialized) return null;
 *   // use axios…
 * };
 * ```
 */

// =============================================================================
// Core Types
// =============================================================================

export type {
  HttpClientConfig,
  HttpRetryConfig,
  HttpCircuitBreakerConfig,
  AuthConfig,
  ClientHeadersConfig,
  ResolvedHttpConfig,
  HttpContextValue,
  HttpProviderProps,
} from './core/types';

// =============================================================================
// Core Constants
// =============================================================================

export {
  DEFAULT_TIMEOUT_MS,
  UPLOAD_TIMEOUT_MS,
  DOWNLOAD_TIMEOUT_MS,
  DEFAULT_HTTP_RETRY_CONFIG,
  DEFAULT_HTTP_CIRCUIT_BREAKER_CONFIG,
  DEFAULT_AUTH_CONFIG,
  HTTP_HEADERS,
  CLIENT_HEADERS,
  CONTENT_TYPES,
  HTTP_STATUS,
  HTTP_ERROR_CODE,
  type HttpErrorCode,
  PARAMS_ARRAY_FORMAT,
  type ParamsArrayFormat,
  SERIALIZATION_OPERATION,
  type SerializationOperation,
  AXIOS_ERROR_CODE,
} from './core/constants';

// =============================================================================
// Provider & Hooks
// =============================================================================

export { HttpProvider } from './provider/http-provider';
export { HttpContext, useHttpContext } from './provider/http-context';
export { useHttp } from './hooks/use-http';

// =============================================================================
// Error Classes
// =============================================================================

export {
  HttpError,
  HttpNotInitializedError,
  HttpRequestError,
  HttpTimeoutError,
  HttpNetworkError,
  HttpCancelledError,
  HttpUnauthorizedError,
  HttpForbiddenError,
  HttpNotFoundError,
  HttpServerError,
  HttpConfigError,
  HttpSerializationError,
} from './errors/http-errors';

// =============================================================================
// Error Type Guards
// =============================================================================

export {
  isHttpError,
  hasHttpErrorCode,
  isHttpNotInitializedError,
  isHttpRequestError,
  isHttpTimeoutError,
  isHttpNetworkError,
  isHttpCancelledError,
  isHttpUnauthorizedError,
  isHttpForbiddenError,
  isHttpNotFoundError,
  isHttpServerError,
  isHttpConfigError,
  isHttpSerializationError,
  isAuthenticationError,
  isClientError,
  isServerError,
  isRetryableHttpError,
  isNonRetryableHttpError,
} from './errors/type-guards';

// =============================================================================
// Instance Factory & Management
// =============================================================================

export {
  createAxiosInstance,
  createConfiguredAxiosInstance,
  resolveHttpConfig,
} from './instance/axios-factory';

export {
  httpInstanceManager,
  getDefaultAxiosInstance,
  getAxiosInstance,
} from './instance/instance-manager';

// =============================================================================
// Circuit Breaker
// =============================================================================

export {
  CircuitBreaker,
  createCircuitBreakerInterceptor,
  createCircuitBreakerRequestInterceptor,
  setupCircuitBreakerInterceptor,
  DEFAULT_CIRCUIT_BREAKER_CONFIG,
  type CircuitBreakerConfig,
  type CircuitBreakerInterceptorOptions,
} from './interceptors/response/circuit-breaker-interceptor';
