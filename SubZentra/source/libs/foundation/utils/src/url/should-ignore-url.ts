/**
 * Check if URL should be ignored
 * @module url/should-ignore-url
 */

/**
 * Check if URL matches any of the ignore patterns
 * @param url - URL to check
 * @param patterns - Array of patterns (regex strings or plain strings)
 * @returns true if URL should be ignored
 */
export const shouldIgnoreUrl = (url: string, patterns: string[]): boolean => {
  if (patterns.length === 0) {
    return false;
  }

  return patterns.some((pattern) => {
    try {
      const regex = new RegExp(pattern);
      return regex.test(url);
    } catch {
      return url.includes(pattern);
    }
  });
};
