/**
 * Semantic Background Tokens - Tier 2
 * Usage-based background colors for consistent UI
 *
 * These tokens reference primitives and provide semantic meaning
 * for different UI contexts and states.
 *
 * @module tokens/semantic/backgrounds
 */

/**
 * Layer system for depth hierarchy
 *
 * Linear-inspired layering:
 * - layer00: Deepest background (canvas)
 * - layer01: Default surface (cards, panels)
 * - layer02: Elevated surface (dropdowns, popovers)
 * - layer03: Highest elevation (modals, dialogs)
 * - overlay: Backdrop for modals
 */
export const backgroundLayers = {
  /** Deepest background - app canvas */
  layer00: 'var(--color-neutral-100)',
  /** Default surface - cards, panels */
  layer01: 'var(--color-neutral-120)',
  /** Elevated surface - dropdowns */
  layer02: 'var(--color-neutral-140)',
  /** Highest elevation - modals */
  layer03: 'var(--color-neutral-160)',
  /** Overlay backdrop */
  overlay: 'hsla(var(--neutral-h, 228) var(--neutral-s, 6)% 8% / 0.8)',
} as const;

/**
 * Interactive state type definition
 */
export interface InteractiveStateTokens {
  readonly resting: string;
  readonly hovered: string;
  readonly pressed: string;
  readonly disabled?: string;
}

/**
 * Interactive background tokens
 *
 * Button and control states following Linear UX:
 * - Subtle hover states (not jarring)
 * - Clear pressed feedback
 * - Obvious disabled states
 */
export const backgroundInteractive = {
  /** Primary action (accent color) */
  primary: {
    resting: 'var(--color-accent-500)',
    hovered: 'var(--color-accent-440)',
    pressed: 'var(--color-accent-560)',
    disabled: 'var(--color-accent-700)',
  } satisfies InteractiveStateTokens,

  /** Secondary action (neutral) */
  secondary: {
    resting: 'var(--color-neutral-220)',
    hovered: 'var(--color-neutral-240)',
    pressed: 'var(--color-neutral-280)',
    disabled: 'var(--color-neutral-180)',
  } satisfies InteractiveStateTokens,

  /** Tertiary/ghost action */
  tertiary: {
    resting: 'transparent',
    hovered: 'var(--color-neutral-180)',
    pressed: 'var(--color-neutral-220)',
    disabled: 'transparent',
  } satisfies InteractiveStateTokens,

  /** Destructive action */
  destructive: {
    resting: 'var(--color-alert-500)',
    hovered: 'var(--color-alert-440)',
    pressed: 'var(--color-alert-560)',
    disabled: 'var(--color-alert-700)',
  } satisfies InteractiveStateTokens,

  /** Smart/AI action */
  smart: {
    resting: 'var(--color-smart-500)',
    hovered: 'var(--color-smart-440)',
    pressed: 'var(--color-smart-560)',
    disabled: 'var(--color-smart-700)',
  } satisfies InteractiveStateTokens,
} as const;

/**
 * Navigation background tokens
 */
export const backgroundNavigation = {
  /** Sidebar/navigation background */
  sidebar: 'var(--color-neutral-100)',
  /** Navigation item hover */
  itemHovered: 'var(--color-neutral-180)',
  /** Navigation item pressed */
  itemPressed: 'var(--color-neutral-220)',
  /** Navigation item selected */
  itemSelected: 'var(--color-neutral-200)',
  /** Navigation item selected + hovered */
  itemSelectedHovered: 'var(--color-neutral-220)',
} as const;

/**
 * Input field background tokens
 */
export const backgroundInput = {
  /** Default input background */
  default: 'var(--color-neutral-100)',
  /** Input on hover */
  hovered: 'var(--color-neutral-120)',
  /** Input when focused */
  focused: 'var(--color-neutral-80)',
  /** Disabled input */
  disabled: 'var(--color-neutral-160)',
  /** Input with error */
  error: 'hsla(var(--alert-h, 0) var(--alert-s, 72)% 50% / 0.1)',
} as const;

/**
 * Feedback/status background tokens
 */
export const backgroundFeedback = {
  /** Success state background */
  success: 'hsla(var(--success-h, 142) var(--success-s, 55)% 50% / 0.15)',
  /** Warning state background */
  warning: 'hsla(var(--warning-h, 45) var(--warning-s, 74)% 50% / 0.15)',
  /** Error state background */
  error: 'hsla(var(--alert-h, 0) var(--alert-s, 72)% 50% / 0.15)',
  /** Info state background */
  info: 'hsla(var(--info-h, 210) var(--info-s, 80)% 50% / 0.15)',
  /** Smart/AI indicator background */
  smart: 'hsla(var(--smart-h, 256) var(--smart-s, 94)% 50% / 0.15)',
} as const;

/**
 * Miscellaneous background tokens
 */
export const backgroundMisc = {
  /** Skeleton loading placeholder */
  skeleton: 'var(--color-neutral-200)',
  /** Skeleton shimmer highlight */
  skeletonHighlight: 'var(--color-neutral-240)',
  /** Scrollbar track */
  scrollbar: 'var(--color-neutral-160)',
  /** Scrollbar thumb */
  scrollbarThumb: 'var(--color-neutral-280)',
  /** Scrollbar thumb hover */
  scrollbarThumbHovered: 'var(--color-neutral-360)',
  /** Selection highlight */
  selection: 'hsla(var(--accent-h, 235) var(--accent-s, 56)% 60% / 0.3)',
  /** Code block background */
  code: 'var(--color-neutral-140)',
  /** Badge/chip background */
  badge: 'var(--color-neutral-200)',
  /** Tooltip background */
  tooltip: 'var(--color-neutral-160)',
} as const;

/**
 * Combined background semantic tokens
 */
export const backgroundTokens = {
  layer: backgroundLayers,
  interactive: backgroundInteractive,
  navigation: backgroundNavigation,
  input: backgroundInput,
  feedback: backgroundFeedback,
  misc: backgroundMisc,
} as const;

/**
 * Type exports
 */
export type BackgroundLayerKey = keyof typeof backgroundLayers;
export type BackgroundInteractiveKey = keyof typeof backgroundInteractive;
export type BackgroundFeedbackKey = keyof typeof backgroundFeedback;
