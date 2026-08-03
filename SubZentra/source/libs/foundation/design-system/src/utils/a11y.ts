/**
 * Accessibility utilities
 * @module utils/a11y
 */

/**
 * Generates a unique ID for accessibility purposes
 * Used for aria-labelledby, aria-describedby, etc.
 *
 * @param prefix - Prefix for the ID
 * @returns Unique ID string
 */
let idCounter = 0;
export function generateA11yId(prefix = 'oi'): string {
  return `${prefix}-${++idCounter}`;
}

/**
 * Resets the ID counter (useful for testing)
 */
export function resetA11yIdCounter(): void {
  idCounter = 0;
}

/**
 * Props for screen reader only content
 */
export const visuallyHiddenStyles: React.CSSProperties = {
  position: 'absolute',
  width: '1px',
  height: '1px',
  padding: '0',
  margin: '-1px',
  overflow: 'hidden',
  clip: 'rect(0, 0, 0, 0)',
  whiteSpace: 'nowrap',
  border: '0',
};

/**
 * Tailwind classes for visually hidden content (screen reader only)
 */
export const visuallyHiddenClasses =
  'absolute w-px h-px p-0 -m-px overflow-hidden whitespace-nowrap border-0';

/**
 * Checks if focus should be visible (keyboard navigation)
 * Returns true if the user is navigating with keyboard
 */
export function shouldShowFocusRing(): boolean {
  // Check if there's a focus-visible polyfill or native support
  if (typeof document === 'undefined') return false;

  // Check for the :focus-visible pseudo-class support
  try {
    document.querySelector(':focus-visible');
    return true;
  } catch {
    return false;
  }
}

/**
 * Keyboard keys commonly used in accessibility
 */
export const A11yKeys = {
  Enter: 'Enter',
  Space: ' ',
  Escape: 'Escape',
  Tab: 'Tab',
  ArrowUp: 'ArrowUp',
  ArrowDown: 'ArrowDown',
  ArrowLeft: 'ArrowLeft',
  ArrowRight: 'ArrowRight',
  Home: 'Home',
  End: 'End',
  PageUp: 'PageUp',
  PageDown: 'PageDown',
} as const;

export type A11yKey = (typeof A11yKeys)[keyof typeof A11yKeys];

/**
 * Checks if an event key matches one of the provided keys
 *
 * @param event - Keyboard event
 * @param keys - Keys to check
 * @returns true if the event key matches any of the provided keys
 */
export function isKey(event: { key: string }, ...keys: A11yKey[]): boolean {
  return keys.includes(event.key as A11yKey);
}

/**
 * Type for elements that can receive focus
 */
export type FocusableElement =
  | HTMLButtonElement
  | HTMLInputElement
  | HTMLSelectElement
  | HTMLTextAreaElement
  | HTMLAnchorElement
  | HTMLElement;

/**
 * Selector for focusable elements
 */
export const focusableSelector = [
  'button:not([disabled])',
  '[href]',
  'input:not([disabled])',
  'select:not([disabled])',
  'textarea:not([disabled])',
  '[tabindex]:not([tabindex="-1"])',
].join(', ');

/**
 * Gets all focusable elements within a container
 *
 * @param container - Container element
 * @returns Array of focusable elements
 */
export function getFocusableElements(container: HTMLElement): FocusableElement[] {
  return Array.from(container.querySelectorAll<FocusableElement>(focusableSelector));
}

/**
 * Traps focus within a container (for modals, dialogs)
 *
 * @param container - Container element
 * @param event - Keyboard event
 */
export function trapFocus(container: HTMLElement, event: KeyboardEvent): void {
  if (event.key !== 'Tab') return;

  const focusableElements = getFocusableElements(container);
  if (focusableElements.length === 0) return;

  const firstElement = focusableElements[0];
  const lastElement = focusableElements[focusableElements.length - 1];

  if (event.shiftKey && document.activeElement === firstElement) {
    event.preventDefault();
    lastElement.focus();
  } else if (!event.shiftKey && document.activeElement === lastElement) {
    event.preventDefault();
    firstElement.focus();
  }
}

/**
 * Announces a message to screen readers using a live region
 *
 * @param message - Message to announce
 * @param priority - 'polite' or 'assertive'
 */
export function announceToScreenReader(
  message: string,
  priority: 'polite' | 'assertive' = 'polite',
): void {
  if (typeof document === 'undefined') return;

  const announcement = document.createElement('div');
  announcement.setAttribute('role', 'status');
  announcement.setAttribute('aria-live', priority);
  announcement.setAttribute('aria-atomic', 'true');
  Object.assign(announcement.style, visuallyHiddenStyles);
  announcement.textContent = message;

  document.body.appendChild(announcement);

  // Remove after announcement is made
  setTimeout(() => {
    document.body.removeChild(announcement);
  }, 1000);
}

/**
 * Props for components that can be disabled
 */
export interface DisableableProps {
  /** Whether the component is disabled */
  disabled?: boolean;
  /** ARIA disabled attribute (maintains focusability) */
  'aria-disabled'?: boolean;
}

/**
 * Gets the effective disabled state for a component
 * Prefers aria-disabled over disabled for better screen reader support
 *
 * @param props - Component props
 * @returns Effective disabled state
 */
export function getDisabledState(props: DisableableProps): boolean {
  return props['aria-disabled'] ?? props.disabled ?? false;
}
