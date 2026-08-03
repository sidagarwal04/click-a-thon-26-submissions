/**
 * Validation types for structured validation results
 *
 * Provides a consistent interface for validation across the codebase,
 * with support for multiple issues, severity levels, and suggestions.
 *
 * @module types/validation
 */

import type { ValueOf } from './utility';

// =============================================================================
// Types
// =============================================================================

/**
 * Severity level for validation issues
 */
export const VALIDATION_SEVERITY = {
  ERROR: 'error',
  WARNING: 'warning',
} as const;

export type ValidationSeverity = ValueOf<typeof VALIDATION_SEVERITY>;

/**
 * A single validation issue
 */
export interface ValidationIssue {
  /** JSONPath-like path to the field with the issue (e.g., "user.email", "items[0].name") */
  readonly path: string;
  /** Human-readable message describing the issue */
  readonly message: string;
  /** Severity of the issue */
  readonly severity: ValidationSeverity;
  /** Optional suggestion for fixing the issue */
  readonly suggestion?: string;
  /** Optional error code for programmatic handling */
  readonly code?: string;
}

/**
 * Result of a validation operation
 */
export interface ValidationResultData {
  /** Whether validation passed (no errors, may have warnings) */
  readonly valid: boolean;
  /** List of validation issues found */
  readonly issues: ReadonlyArray<ValidationIssue>;
}

// =============================================================================
// Validation Result Utilities
// =============================================================================

/**
 * ValidationResult constructor and utility functions
 *
 * Provides functional utilities for working with validation results.
 */
export const ValidationResult = {
  /**
   * Create a successful validation result
   *
   * @returns A valid ValidationResult with no issues
   *
   * @example
   * ```typescript
   * const result = ValidationResult.success();
   * // { valid: true, issues: [] }
   * ```
   */
  success: (): ValidationResultData => ({
    valid: true,
    issues: [],
  }),

  /**
   * Create a failed validation result
   *
   * @param issues - Array of validation issues
   * @returns A failed ValidationResult with the given issues
   *
   * @example
   * ```typescript
   * const result = ValidationResult.failure([
   *   { path: 'email', message: 'Invalid email format', severity: 'error' }
   * ]);
   * ```
   */
  failure: (issues: ValidationIssue[]): ValidationResultData => ({
    valid: false,
    issues,
  }),

  /**
   * Create a validation result with warnings (valid but with warnings)
   *
   * @param issues - Array of warning issues
   * @returns A valid ValidationResult with warning issues
   *
   * @example
   * ```typescript
   * const result = ValidationResult.withWarnings([
   *   { path: 'name', message: 'Name is short', severity: 'warning' }
   * ]);
   * ```
   */
  withWarnings: (issues: ValidationIssue[]): ValidationResultData => ({
    valid: true,
    issues: issues.map((issue) => ({ ...issue, severity: VALIDATION_SEVERITY.WARNING })),
  }),

  /**
   * Create a validation result from an array of error messages (backward compatibility)
   *
   * @param errors - Array of error message strings
   * @param path - Optional path prefix for all errors
   * @returns A ValidationResult
   *
   * @example
   * ```typescript
   * const result = ValidationResult.fromErrors(['Invalid email', 'Password too short']);
   * ```
   */
  fromErrors: (errors: string[], path = ''): ValidationResultData => {
    if (errors.length === 0) {
      return { valid: true, issues: [] };
    }
    return {
      valid: false,
      issues: errors.map((message) => ({
        path,
        message,
        severity: VALIDATION_SEVERITY.ERROR,
      })),
    };
  },

  /**
   * Create a single-error validation result
   *
   * @param path - Path to the field with the error
   * @param message - Error message
   * @param options - Optional code and suggestion
   * @returns A failed ValidationResult
   *
   * @example
   * ```typescript
   * const result = ValidationResult.error('email', 'Invalid email format', {
   *   code: 'INVALID_EMAIL',
   *   suggestion: 'Please enter a valid email address'
   * });
   * ```
   */
  error: (
    path: string,
    message: string,
    options?: { code?: string; suggestion?: string },
  ): ValidationResultData => ({
    valid: false,
    issues: [
      {
        path,
        message,
        severity: VALIDATION_SEVERITY.ERROR,
        code: options?.code,
        suggestion: options?.suggestion,
      },
    ],
  }),

  /**
   * Create a single-warning validation result
   *
   * @param path - Path to the field with the warning
   * @param message - Warning message
   * @param options - Optional code and suggestion
   * @returns A valid ValidationResult with a warning
   */
  warning: (
    path: string,
    message: string,
    options?: { code?: string; suggestion?: string },
  ): ValidationResultData => ({
    valid: true,
    issues: [
      {
        path,
        message,
        severity: VALIDATION_SEVERITY.WARNING,
        code: options?.code,
        suggestion: options?.suggestion,
      },
    ],
  }),

  /**
   * Merge multiple validation results into one
   *
   * @param results - Array of validation results to merge
   * @returns A merged ValidationResult
   *
   * @example
   * ```typescript
   * const combined = ValidationResult.merge(
   *   validateEmail(data.email),
   *   validatePassword(data.password),
   *   validateUsername(data.username)
   * );
   * ```
   */
  merge: (...results: ValidationResultData[]): ValidationResultData => {
    const issues: ValidationIssue[] = [];
    let valid = true;

    for (const result of results) {
      issues.push(...result.issues);
      if (!result.valid) {
        valid = false;
      }
    }

    return { valid, issues };
  },

  /**
   * Check if a validation result is valid
   *
   * @param result - The validation result to check
   * @returns True if the result is valid
   */
  isValid: (result: ValidationResultData): boolean => result.valid,

  /**
   * Get only error issues from a validation result
   *
   * @param result - The validation result
   * @returns Array of error issues only
   */
  getErrors: (result: ValidationResultData): ReadonlyArray<ValidationIssue> =>
    result.issues.filter((issue) => issue.severity === VALIDATION_SEVERITY.ERROR),

  /**
   * Get only warning issues from a validation result
   *
   * @param result - The validation result
   * @returns Array of warning issues only
   */
  getWarnings: (result: ValidationResultData): ReadonlyArray<ValidationIssue> =>
    result.issues.filter((issue) => issue.severity === VALIDATION_SEVERITY.WARNING),

  /**
   * Check if a validation result has any errors
   *
   * @param result - The validation result
   * @returns True if there are any error issues
   */
  hasErrors: (result: ValidationResultData): boolean =>
    result.issues.some((issue) => issue.severity === VALIDATION_SEVERITY.ERROR),

  /**
   * Check if a validation result has any warnings
   *
   * @param result - The validation result
   * @returns True if there are any warning issues
   */
  hasWarnings: (result: ValidationResultData): boolean =>
    result.issues.some((issue) => issue.severity === VALIDATION_SEVERITY.WARNING),

  /**
   * Map validation result to a different format
   *
   * @param result - The validation result
   * @param fn - Function to transform issues
   * @returns Transformed validation result
   */
  mapIssues: (
    result: ValidationResultData,
    fn: (issue: ValidationIssue) => ValidationIssue,
  ): ValidationResultData => ({
    valid: result.valid,
    issues: result.issues.map(fn),
  }),

  /**
   * Prefix all paths in a validation result
   *
   * @param result - The validation result
   * @param prefix - Prefix to add to all paths
   * @returns Validation result with prefixed paths
   *
   * @example
   * ```typescript
   * const nested = ValidationResult.prefixPaths(
   *   validateAddress(data.address),
   *   'address'
   * );
   * // paths: 'address.street', 'address.city', etc.
   * ```
   */
  prefixPaths: (result: ValidationResultData, prefix: string): ValidationResultData => ({
    valid: result.valid,
    issues: result.issues.map((issue) => ({
      ...issue,
      path: issue.path ? `${prefix}.${issue.path}` : prefix,
    })),
  }),

  /**
   * Format validation result as an error message string
   *
   * @param result - The validation result
   * @param separator - Separator between messages (default: ', ')
   * @returns Formatted error message or empty string if valid
   */
  formatErrors: (result: ValidationResultData, separator = ', '): string => {
    const errors = result.issues.filter((issue) => issue.severity === VALIDATION_SEVERITY.ERROR);
    if (errors.length === 0) return '';
    return errors
      .map((issue) => (issue.path ? `${issue.path}: ${issue.message}` : issue.message))
      .join(separator);
  },

  /**
   * Convert validation result to a record of errors by path
   *
   * @param result - The validation result
   * @returns Record mapping paths to error messages
   *
   * @example
   * ```typescript
   * const errorsByPath = ValidationResult.toErrorMap(result);
   * // { email: 'Invalid email', password: 'Too short' }
   * ```
   */
  toErrorMap: (result: ValidationResultData): Record<string, string> => {
    const map: Record<string, string> = {};
    for (const issue of result.issues) {
      if (issue.severity === VALIDATION_SEVERITY.ERROR && issue.path) {
        map[issue.path] = issue.message;
      }
    }
    return map;
  },
};

// NOTE: ValidationResult is exported as a const object with utility methods.
// For the type, use ValidationResultData.
// Example:
//   import { ValidationResult } from './validation';
//   import type { ValidationResultData } from './validation';
//
//   const result: ValidationResultData = ValidationResult.success();
