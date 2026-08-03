/**
 * Semantic Text Tokens - Tier 2
 * Usage-based text colors with accessibility considerations
 *
 * Color hierarchy designed for WCAG AA compliance
 * against both dark and light backgrounds.
 *
 * @module tokens/semantic/text
 */

/**
 * Text color hierarchy
 *
 * Following Linear's text hierarchy:
 * - highlight: Maximum emphasis (100% contrast)
 * - primary: Default text (high contrast)
 * - secondary: Reduced emphasis
 * - tertiary: Placeholder/hint text
 * - muted: Disabled/subtle text
 * - inverted: Text on colored backgrounds
 */
export const textColors = {
  /** Maximum emphasis - headings, important text */
  highlight: 'var(--color-static-mercuryWhite)',
  /** Primary text - default content */
  primary: 'var(--color-neutral-940)',
  /** Secondary text - reduced emphasis */
  secondary: 'var(--color-neutral-740)',
  /** Tertiary text - placeholders, hints */
  tertiary: 'var(--color-neutral-620)',
  /** Muted text - disabled, subtle */
  muted: 'var(--color-neutral-400)',
  /** Inverted text - on colored backgrounds */
  inverted: 'var(--color-neutral-80)',
} as const;

/**
 * Static text colors (mode-independent)
 */
export const textStatic = {
  /** Always white */
  white: 'var(--color-static-white)',
  /** Always black */
  black: 'var(--color-static-black)',
  /** Mercury white (Linear brand) */
  mercuryWhite: 'var(--color-static-mercuryWhite)',
  /** Nordic gray (Linear brand) */
  nordicGray: 'var(--color-static-nordicGray)',
} as const;

/**
 * Interactive text colors
 * For buttons, links, and other interactive elements
 */
export const textInteractive = {
  /** Primary button text */
  primary: {
    resting: 'var(--color-static-white)',
    disabled: 'var(--color-neutral-560)',
  },
  /** Secondary button text */
  secondary: {
    resting: 'var(--color-neutral-940)',
    hovered: 'var(--color-neutral-1000)',
    disabled: 'var(--color-neutral-480)',
  },
  /** Tertiary/ghost button text */
  tertiary: {
    resting: 'var(--color-neutral-740)',
    hovered: 'var(--color-neutral-940)',
    active: 'var(--color-neutral-1000)',
    disabled: 'var(--color-neutral-400)',
  },
  /** Destructive button text */
  destructive: {
    resting: 'var(--color-static-white)',
    disabled: 'var(--color-neutral-560)',
  },
  /** Smart/AI button text */
  smart: {
    resting: 'var(--color-static-white)',
    disabled: 'var(--color-neutral-560)',
  },
} as const;

/**
 * Link text colors
 */
export const textLink = {
  /** Default link */
  default: 'var(--color-accent-500)',
  /** Hovered link */
  hovered: 'var(--color-accent-440)',
  /** Visited link */
  visited: 'var(--color-accent-620)',
  /** Active/pressed link */
  active: 'var(--color-accent-560)',
} as const;

/**
 * Navigation text colors
 */
export const textNavigation = {
  /** Default nav item */
  default: 'var(--color-neutral-740)',
  /** Hovered nav item */
  hovered: 'var(--color-neutral-940)',
  /** Selected/active nav item */
  selected: 'var(--color-neutral-1000)',
  /** Pressed nav item */
  pressed: 'var(--color-neutral-940)',
} as const;

/**
 * Input text colors
 */
export const textInput = {
  /** Input value text */
  value: 'var(--color-neutral-940)',
  /** Placeholder text */
  placeholder: 'var(--color-neutral-480)',
  /** Disabled input text */
  disabled: 'var(--color-neutral-400)',
  /** Label text */
  label: 'var(--color-neutral-740)',
  /** Helper text */
  helper: 'var(--color-neutral-620)',
} as const;

/**
 * Feedback/status text colors
 */
export const textFeedback = {
  /** Success text */
  success: 'var(--color-success-500)',
  /** Warning text */
  warning: 'var(--color-warning-500)',
  /** Error text */
  error: 'var(--color-alert-500)',
  /** Info text */
  info: 'var(--color-info-500)',
  /** Smart/AI text */
  smart: 'var(--color-smart-500)',
} as const;

/**
 * Accent/brand text colors
 */
export const textAccent = {
  /** Primary accent */
  primary: 'var(--color-accent-500)',
  /** Secondary accent (lighter) */
  secondary: 'var(--color-accent-620)',
  /** Muted accent */
  muted: 'var(--color-accent-700)',
} as const;

/**
 * Code/monospace text colors
 */
export const textCode = {
  /** Default code text */
  default: 'var(--color-neutral-860)',
  /** Keyword */
  keyword: 'var(--color-accent-500)',
  /** String */
  string: 'var(--color-success-500)',
  /** Number */
  number: 'var(--color-warning-500)',
  /** Comment */
  comment: 'var(--color-neutral-480)',
  /** Function */
  function: 'var(--color-info-500)',
  /** Operator */
  operator: 'var(--color-neutral-620)',
} as const;

/**
 * Combined text semantic tokens
 */
export const textTokens = {
  color: textColors,
  static: textStatic,
  interactive: textInteractive,
  link: textLink,
  navigation: textNavigation,
  input: textInput,
  feedback: textFeedback,
  accent: textAccent,
  code: textCode,
} as const;

/**
 * Type exports
 */
export type TextColorKey = keyof typeof textColors;
export type TextFeedbackKey = keyof typeof textFeedback;
