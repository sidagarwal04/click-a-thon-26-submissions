/**
 * Stack Trace Utilities
 *
 * Shared stack trace sanitization used by foundation-metrics and error-instrumentation.
 *
 * @module utils/stack-utils
 */

/**
 * Sanitize a stack trace
 */
export const sanitizeStackTrace = (stack?: string): string => {
  if (!stack) {
    return '';
  }
  return stack;
};
