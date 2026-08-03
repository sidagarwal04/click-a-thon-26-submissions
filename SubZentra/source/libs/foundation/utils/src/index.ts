/**
 * Foundation Utils
 *
 * Common utility functions for the Open Zentra Web platform.
 * Contains only generic, widely-applicable utilities.
 *
 * @module @open-zentra/foundation-utils
 */

// Browser utilities
export {
  isBrowser,
  detectBrowser,
  detectBrowserAsync,
  DETECTION_METHOD,
  DEVICE_TYPE,
  EFFECTIVE_CONNECTION_TYPE,
  type BrowserInfo,
  type DetectionMethod,
  type DeviceType,
  type EffectiveConnectionType,
} from './browser';

// URL utilities
export {
  sanitizeUrl,
  extractRoute,
  shouldIgnoreUrl,
  isSameOrigin,
  getCurrentPageUrl,
  getCurrentRoute,
  shouldPropagateTraceContext,
  DEFAULT_SANITIZATION_OPTIONS,
  type URLSanitizationOptions,
} from './url';

// Hash and ID utilities
export { hashStringSync, generateId, hashPayloadSync, hashPayloadAsync } from './hash';

// Logger utilities
export {
  Logger,
  createLogger,
  createDebugLogger,
  LOG_LEVEL,
  LOG_LEVEL_PRIORITY,
  type LogLevel,
  type LogHandler,
  type LoggerConfig,
} from './logger';

// Concurrency utilities
export { Mutex, Semaphore } from './concurrency';

// Singleton utilities
export {
  createSingletonFactory,
  createAsyncSingletonFactory,
  createDeepEqualComparison,
  type SingletonFactoryConfig,
  type SingletonFactory,
  type ConfigComparisonResult,
} from './singleton';

// Assertion utilities
export {
  assert,
  assertDefined,
  assertNotNull,
  assertType,
  assertNever,
  assertNonEmpty,
  assertInRange,
} from './assert';

// Async utilities
export {
  createDeferred,
  createDeferredWithTimeout,
  sleep,
  createTimeoutPromise,
  withTimeout,
  runSequentially,
  runWithConcurrency,
  type Deferred,
  type TimeoutPromiseResult,
} from './async';

// Error utilities
export {
  normalizeError,
  formatErrorMessage,
  getErrorMessage,
  getErrorName,
  isErrorType,
  isAbortError,
  isNetworkError,
  isTimeoutError,
  isTypeError,
  isSyntaxError,
  isRangeError,
  hasErrorCode,
  isRetriableHttpStatus,
  createErrorHandler,
  type ErrorHandlerConfig,
} from './error';

// Object utilities
export { deepFreeze, isDeeplyFrozen } from './object';

// Validation utilities
export {
  isPositiveInteger,
  isNonNegative,
  isNonNegativeInteger,
  isFiniteNumber,
  isInRange,
  isValidPercentage,
  isValidPort,
} from './validation';

// OPFS utilities
export {
  isOpfsSupported,
  getOpfsRootDirectory,
  createDirectoryPath,
  getDirectoryAtPath,
  fileExistsInOpfs,
  listDirectoryEntries,
  clearDirectory,
} from './opfs';

// Algorithm utilities
export { topologicalSort, hasCircularDependency } from './algorithm';

// Disposable pattern utilities
export {
  type IDisposable,
  type IAsyncDisposable,
  Disposable,
  AsyncDisposable,
  CompositeDisposable,
  DisposedError,
  createDisposable,
  using,
  usingAsync,
} from './disposable';

// Timer utilities
export {
  // Constants
  TIME_MS,
  TIMER_DEFAULTS,
  TIMER_STATE,
  // Types
  type TimerState,
  type TimerStats,
  type SafeTimerConfig,
  type ManagedIntervalConfig,
  type IntervalStats,
  type SafeDebounceConfig,
  type DebounceStats,
  type ITimer,
  type IDebounce,
  type DebouncedFunction,
  // SafeTimer
  SafeTimer,
  createSafeTimer,
  createOneShotTimer,
  // ManagedInterval
  ManagedInterval,
  createManagedInterval,
  // SafeDebounce
  SafeDebounce,
  createSafeDebounce,
  debounce,
} from './timer';

// Constants (stable references)
export { EMPTY_ARRAY, EMPTY_OBJECT, EMPTY_MAP, EMPTY_SET } from './constants';
