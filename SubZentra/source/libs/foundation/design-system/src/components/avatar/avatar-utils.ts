/**
 * Avatar utility functions
 * @module components/avatar/utils
 */

/**
 * Extracts initials from a name string
 *
 * @param name - Full name string
 * @param maxLength - Maximum number of initials to return (default: 2)
 * @returns Uppercase initials
 *
 * @example
 * getInitials('John Doe') // 'JD'
 * getInitials('Alice') // 'A'
 * getInitials('Alice Bob Charlie', 2) // 'AC'
 */
export function getInitials(name: string, maxLength = 2): string {
  if (!name || typeof name !== 'string') {
    return '';
  }

  const words = name.trim().split(/\s+/).filter(Boolean);

  if (words.length === 0) {
    return '';
  }

  if (words.length === 1) {
    return words[0].charAt(0).toUpperCase();
  }

  // Take first and last word's initials
  const initials = [words[0].charAt(0), words[words.length - 1].charAt(0)].join('').toUpperCase();

  return initials.slice(0, maxLength);
}

/**
 * Generates a consistent color based on a string (for fallback backgrounds)
 *
 * @param str - Input string (usually the name)
 * @returns HSL color string
 */
export function stringToColor(str: string): string {
  if (!str) return 'hsl(0, 0%, 60%)';

  let hash = 0;
  for (let i = 0; i < str.length; i++) {
    hash = str.charCodeAt(i) + ((hash << 5) - hash);
  }

  const hue = Math.abs(hash % 360);
  return `hsl(${hue}, 65%, 55%)`;
}

/**
 * Generates a unique ID for SVG masks
 *
 * @param prefix - Optional prefix for the ID
 * @returns Unique ID string
 */
export function generateMaskId(prefix = 'avatar-mask'): string {
  return `${prefix}-${Math.random().toString(36).slice(2, 11)}`;
}
