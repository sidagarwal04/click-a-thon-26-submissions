/**
 * Centralized error handler utility
 * @module error/error-handler
 */
import { normalizeError } from './normalize-error';

/**
 * Configuration for creating a scoped error handler
 */
export interface ErrorHandlerConfig {
  /** Context name for logging (e.g., component or module name) */
  context: string;
  /** Enable debug logging */
  debug?: boolean;
  /** External error callback for error reporting */
  onError?: (error: Error, context?: string) => void;
  /** Whether to rethrow the error after handling */
  rethrow?: boolean;
}

/**
 * Create a scoped error handler
 *
 * Creates a reusable error handler function bound to a specific context.
 * Useful for creating module-level error handlers.
 *
 * @param config - Error handler configuration
 * @returns A function that handles errors with the configured behavior
 *
 * @example
 * ```typescript
 * const handleError = createErrorHandler({
 *   context: 'UserService',
 *   debug: true,
 *   onError: (error, ctx) => errorReporter.capture(error, { context: ctx }),
 * });
 *
 * try {
 *   await fetchUser();
 * } catch (error) {
 *   handleError(error, 'fetchUser');
 * }
 * ```
 */
export const createErrorHandler = (config: ErrorHandlerConfig) => {
  const { context, debug = false, onError, rethrow = false } = config;

  return (error: unknown, subContext?: string): void => {
    const normalizedError = normalizeError(error);
    const fullContext = subContext ? `${context}.${subContext}` : context;

    if (debug) {
      console.error(`[${fullContext}]`, normalizedError);
    }

    onError?.(normalizedError, fullContext);

    if (rethrow) {
      throw normalizedError;
    }
  };
};
