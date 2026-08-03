/**
 * Semantic Border Tokens - Tier 2
 * Usage-based border colors and styles
 *
 * @module tokens/semantic/borders
 */

/**
 * Border color tokens
 *
 * Hierarchy:
 * - subtle: Barely visible, for grouping
 * - default: Standard borders
 * - emphasis: Highlighted borders
 * - focus: Focus ring color
 */
export const borderColors = {
  /** Subtle border - minimal visual weight */
  subtle: 'var(--color-neutral-160)',
  /** Default border */
  default: 'var(--color-neutral-180)',
  /** Emphasized border */
  emphasis: 'var(--color-neutral-240)',
  /** Strong/heavy border */
  strong: 'var(--color-neutral-320)',
  /** Focus ring color */
  focus: 'var(--color-accent-500)',
  /** Transparent border (for layout consistency) */
  transparent: 'transparent',
} as const;

/**
 * Interactive border states
 */
export const borderInteractive = {
  /** Primary button/input borders */
  primary: {
    resting: 'var(--color-accent-560)',
    hovered: 'var(--color-accent-500)',
    pressed: 'var(--color-accent-620)',
    disabled: 'var(--color-accent-700)',
  },
  /** Secondary borders */
  secondary: {
    resting: 'var(--color-neutral-280)',
    hovered: 'var(--color-neutral-320)',
    pressed: 'var(--color-neutral-400)',
    disabled: 'var(--color-neutral-200)',
  },
  /** Tertiary/ghost borders */
  tertiary: {
    resting: 'transparent',
    hovered: 'var(--color-neutral-240)',
    pressed: 'var(--color-neutral-280)',
    disabled: 'transparent',
  },
  /** Destructive borders */
  destructive: {
    resting: 'var(--color-alert-560)',
    hovered: 'var(--color-alert-500)',
    pressed: 'var(--color-alert-620)',
    disabled: 'var(--color-alert-700)',
  },
  /** Smart/AI borders */
  smart: {
    resting: 'var(--color-smart-560)',
    hovered: 'var(--color-smart-500)',
    pressed: 'var(--color-smart-620)',
    disabled: 'var(--color-smart-700)',
  },
} as const;

/**
 * Input border states
 */
export const borderInput = {
  /** Default input border */
  default: 'var(--color-neutral-220)',
  /** Input hover border */
  hovered: 'var(--color-neutral-280)',
  /** Input focus border */
  focused: 'var(--color-accent-500)',
  /** Disabled input border */
  disabled: 'var(--color-neutral-180)',
  /** Error state border */
  error: 'var(--color-alert-500)',
  /** Success state border */
  success: 'var(--color-success-500)',
  /** Warning state border */
  warning: 'var(--color-warning-500)',
} as const;

/**
 * Navigation borders
 */
export const borderNavigation = {
  /** Tab/navigation item selected indicator */
  selected: 'var(--color-accent-500)',
  /** Tab/navigation item hover indicator */
  hovered: 'var(--color-neutral-400)',
  /** Sidebar border */
  sidebar: 'var(--color-neutral-160)',
} as const;

/**
 * Feedback/status borders
 */
export const borderFeedback = {
  success: 'var(--color-success-500)',
  warning: 'var(--color-warning-500)',
  error: 'var(--color-alert-500)',
  info: 'var(--color-info-500)',
  smart: 'var(--color-smart-500)',
} as const;

/**
 * Separator/divider tokens
 */
export const borderSeparator = {
  /** Light separator */
  light: 'var(--color-neutral-140)',
  /** Default separator */
  default: 'var(--color-neutral-180)',
  /** Strong separator */
  strong: 'var(--color-neutral-240)',
} as const;

/**
 * Border width tokens
 */
export const borderWidths = {
  none: '0',
  thin: '1px',
  default: '1px',
  medium: '2px',
  thick: '3px',
} as const;

/**
 * Border style tokens
 */
export const borderStyles = {
  none: 'none',
  solid: 'solid',
  dashed: 'dashed',
  dotted: 'dotted',
} as const;

/**
 * Combined border semantic tokens
 */
export const borderTokens = {
  color: borderColors,
  interactive: borderInteractive,
  input: borderInput,
  navigation: borderNavigation,
  feedback: borderFeedback,
  separator: borderSeparator,
  width: borderWidths,
  style: borderStyles,
} as const;

/**
 * Type exports
 */
export type BorderColorKey = keyof typeof borderColors;
export type BorderWidthKey = keyof typeof borderWidths;
export type BorderStyleKey = keyof typeof borderStyles;
