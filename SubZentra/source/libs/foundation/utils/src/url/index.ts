/**
 * URL utilities
 * @module url
 */

export { sanitizeUrl } from './sanitize-url';
export { extractRoute } from './extract-route';
export { shouldIgnoreUrl } from './should-ignore-url';
export { isSameOrigin } from './is-same-origin';
export { getCurrentPageUrl } from './get-current-page-url';
export { getCurrentRoute } from './get-current-route';
export { shouldPropagateTraceContext } from './should-propagate-trace-context';
export { type URLSanitizationOptions, DEFAULT_SANITIZATION_OPTIONS } from './types';
