/**
 * URL types
 * @module url/types
 */

/**
 * URL sanitization options
 */
export interface URLSanitizationOptions {
  /** Remove all query parameters */
  removeQueryParams?: boolean;
  /** Query parameters to preserve when removeQueryParams is true */
  preserveQueryParams?: string[];
  /** Remove URL hash/fragment */
  removeHash?: boolean;
  /** Remove authentication (username:password) from URL */
  removeAuth?: boolean;
  /** Remove port number */
  removePort?: boolean;
  /** Patterns to mask in the path (e.g., IDs) */
  maskPathPatterns?: RegExp[];
}

/**
 * Default sanitization options
 */
export const DEFAULT_SANITIZATION_OPTIONS: Required<URLSanitizationOptions> = {
  removeQueryParams: false,
  preserveQueryParams: ['page', 'tab', 'view', 'sort', 'order'],
  removeHash: true,
  removeAuth: true,
  removePort: false,
  maskPathPatterns: [],
};
