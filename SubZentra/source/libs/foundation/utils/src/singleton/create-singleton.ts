/**
 * Singleton factory utility
 *
 * Provides a standardized way to create singleton instances with optional
 * configuration override warnings and reset capabilities for testing.
 *
 * @module singleton/create-singleton
 */

/**
 * Result from config comparison
 */
export interface ConfigComparisonResult {
  /** Whether to show a warning */
  shouldWarn: boolean;
  /** Custom warning message (optional) */
  message?: string;
  /** Whether to throw an error instead of warning */
  shouldThrow?: boolean;
}

/**
 * Configuration for singleton factory
 */
export interface SingletonFactoryConfig<TConfig> {
  /** Name of the singleton for warning messages */
  name: string;
  /** Whether to log warnings when config is ignored (default: true) */
  warnOnConfigOverride?: boolean;
  /**
   * Custom config comparison function
   * If provided, this replaces the default "any config = warn" behavior
   * @param existingConfig - Config used to create current instance
   * @param newConfig - Config being passed to getInstance
   * @returns Whether to warn/throw and optional custom message
   */
  compareConfig?: (
    existingConfig: TConfig | undefined,
    newConfig: TConfig,
  ) => ConfigComparisonResult;
  /** Custom logger function (default: console.warn) */
  logger?: (message: string) => void;
  /** Optional cleanup function called on reset */
  onDispose?: (instance: unknown) => void | Promise<void>;
  /** Default config to use when none provided */
  defaultConfig?: TConfig;
}

/**
 * Result from createSingletonFactory
 */
export interface SingletonFactory<T, TConfig> {
  /** Get or create the singleton instance */
  getInstance: (config?: TConfig) => T;
  /** Reset the singleton instance (for testing) */
  reset: () => Promise<void>;
  /** Check if an instance exists */
  hasInstance: () => boolean;
}

/**
 * Create a singleton factory with configuration override warnings
 *
 * This utility helps DRY up the common singleton pattern found throughout
 * the codebase, providing:
 * - Automatic warning when config is passed to existing instance
 * - Reset capability for testing
 * - Optional cleanup on reset
 *
 * @param createFn - Factory function to create the instance
 * @param factoryConfig - Configuration for the factory behavior
 * @returns Singleton factory with getInstance, reset, and hasInstance methods
 *
 * @example
 * ```typescript
 * interface MyServiceConfig {
 *   debug?: boolean;
 * }
 *
 * class MyService {
 *   constructor(config: MyServiceConfig) { ... }
 *   dispose() { ... }
 * }
 *
 * const myServiceFactory = createSingletonFactory(
 *   (config: MyServiceConfig) => new MyService(config),
 *   {
 *     name: 'MyService',
 *     onDispose: (instance) => (instance as MyService).dispose(),
 *   }
 * );
 *
 * // Get instance
 * const service = myServiceFactory.getInstance({ debug: true });
 *
 * // Second call returns same instance, warns about ignored config
 * const sameService = myServiceFactory.getInstance({ debug: false });
 *
 * // Reset for testing
 * await myServiceFactory.reset();
 * ```
 */
export const createSingletonFactory = <T, TConfig = unknown>(
  createFn: (config: TConfig) => T,
  factoryConfig: SingletonFactoryConfig<TConfig>,
): SingletonFactory<T, TConfig> => {
  let instance: T | null = null;
  let savedConfig: TConfig | undefined = undefined;

  const {
    name,
    warnOnConfigOverride = true,
    compareConfig,
    logger = console.warn,
    onDispose,
    defaultConfig,
  } = factoryConfig;

  const getDefaultMessage = (): string =>
    `[${name}] Instance already exists. ` +
    `Configuration passed to getInstance() will be ignored. ` +
    `Use reset() first if you need to reconfigure.`;

  const getInstance = (config?: TConfig): T => {
    if (instance !== null) {
      // Handle config override warning
      if (config !== undefined) {
        if (compareConfig) {
          // Use custom comparison
          const result = compareConfig(savedConfig, config);
          if (result.shouldThrow) {
            throw new Error(result.message ?? getDefaultMessage());
          }
          if (result.shouldWarn) {
            logger(result.message ?? getDefaultMessage());
          }
        } else if (warnOnConfigOverride) {
          // Default behavior: warn on any config
          logger(getDefaultMessage());
        }
      }
      return instance;
    }

    const finalConfig = config ?? defaultConfig;
    instance = createFn(finalConfig as TConfig);
    savedConfig = finalConfig;
    return instance;
  };

  const reset = async (): Promise<void> => {
    if (instance !== null) {
      if (onDispose) {
        await onDispose(instance);
      }
      instance = null;
      savedConfig = undefined;
    }
  };

  const hasInstance = (): boolean => {
    return instance !== null;
  };

  return {
    getInstance,
    reset,
    hasInstance,
  };
};

/**
 * Create a singleton factory for async initialization
 *
 * Similar to createSingletonFactory but supports async factory functions.
 *
 * @param createFn - Async factory function to create the instance
 * @param factoryConfig - Configuration for the factory behavior
 * @returns Async singleton factory
 *
 * @example
 * ```typescript
 * const dbFactory = createAsyncSingletonFactory(
 *   async (config) => {
 *     const db = new Database(config);
 *     await db.connect();
 *     return db;
 *   },
 *   {
 *     name: 'Database',
 *     onDispose: async (instance) => {
 *       await (instance as Database).disconnect();
 *     },
 *   }
 * );
 *
 * const db = await dbFactory.getInstance({ url: 'localhost' });
 * ```
 */
export const createAsyncSingletonFactory = <T, TConfig = unknown>(
  createFn: (config: TConfig) => Promise<T>,
  factoryConfig: SingletonFactoryConfig<TConfig>,
): {
  getInstance: (config?: TConfig) => Promise<T>;
  reset: () => Promise<void>;
  hasInstance: () => boolean;
} => {
  let instance: T | null = null;
  let initPromise: Promise<T> | null = null;
  let savedConfig: TConfig | undefined = undefined;

  const {
    name,
    warnOnConfigOverride = true,
    compareConfig,
    logger = console.warn,
    onDispose,
    defaultConfig,
  } = factoryConfig;

  const getDefaultMessage = (): string =>
    `[${name}] Instance already exists. ` +
    `Configuration passed to getInstance() will be ignored. ` +
    `Use reset() first if you need to reconfigure.`;

  const getInstance = async (config?: TConfig): Promise<T> => {
    if (instance !== null) {
      // Handle config override warning
      if (config !== undefined) {
        if (compareConfig) {
          // Use custom comparison
          const result = compareConfig(savedConfig, config);
          if (result.shouldThrow) {
            throw new Error(result.message ?? getDefaultMessage());
          }
          if (result.shouldWarn) {
            logger(result.message ?? getDefaultMessage());
          }
        } else if (warnOnConfigOverride) {
          // Default behavior: warn on any config
          logger(getDefaultMessage());
        }
      }
      return instance;
    }

    // Handle concurrent initialization
    if (initPromise !== null) {
      return initPromise;
    }

    const finalConfig = config ?? defaultConfig;
    initPromise = createFn(finalConfig as TConfig);

    try {
      instance = await initPromise;
      savedConfig = finalConfig;
      return instance;
    } finally {
      initPromise = null;
    }
  };

  const reset = async (): Promise<void> => {
    // Wait for any pending initialization
    if (initPromise !== null) {
      try {
        await initPromise;
      } catch {
        // Ignore errors during reset
      }
      initPromise = null;
    }

    if (instance !== null) {
      if (onDispose) {
        await onDispose(instance);
      }
      instance = null;
      savedConfig = undefined;
    }
  };

  const hasInstance = (): boolean => {
    return instance !== null;
  };

  return {
    getInstance,
    reset,
    hasInstance,
  };
};

// =============================================================================
// Helper for config comparison with deep equality
// =============================================================================

/**
 * Create a config comparison function using deep equality (react-fast-compare)
 *
 * Use this with createSingletonFactory when you want to warn only
 * when the config actually differs from the existing one.
 *
 * @param isEqual - Deep equality comparison function
 * @param name - Singleton name for message formatting
 * @returns Config comparison function for SingletonFactoryConfig
 *
 * @example
 * ```typescript
 * import isEqual from 'react-fast-compare';
 *
 * const factory = createSingletonFactory(
 *   (config) => new MyService(config),
 *   {
 *     name: 'MyService',
 *     compareConfig: createDeepEqualComparison(isEqual, 'MyService'),
 *   }
 * );
 * ```
 */
export const createDeepEqualComparison =
  <TConfig>(
    isEqual: (a: unknown, b: unknown) => boolean,
    name: string,
  ): ((existing: TConfig | undefined, provided: TConfig) => ConfigComparisonResult) =>
  (existing, provided) => {
    if (!existing || isEqual(existing, provided)) {
      return { shouldWarn: false };
    }
    return {
      shouldWarn: true,
      message:
        `[${name}] Config ignored - instance already exists. ` +
        `Call reset() first to use new config.`,
    };
  };
