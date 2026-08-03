/**
 * Semantic Effect Tokens - Tier 2
 * Shadows, focus rings, and visual effects
 *
 * Linear-inspired subtle shadows:
 * - Minimal shadow spread for clean look
 * - Color-matched to neutral palette
 * - Depth system for elevation hierarchy
 *
 * @module tokens/semantic/effects
 */

import type { ShadowToken } from '../types';

/**
 * Depth shadow tokens
 *
 * 4-level depth system:
 * - depth01: Subtle lift (cards, buttons)
 * - depth02: Medium elevation (dropdowns)
 * - depth03: High elevation (popovers, toasts)
 * - depth04: Maximum elevation (modals)
 */
export const shadowDepth = {
  /** Level 1: Subtle lift */
  depth01: {
    $type: 'shadow',
    $value: '0 0 2px 0 hsla(228 6% 10% / 0.1), 0 2px 4px 0 hsla(228 6% 10% / 0.05)',
    $description: 'Subtle elevation for cards and buttons',
  } satisfies ShadowToken,

  /** Level 2: Medium elevation */
  depth02: {
    $type: 'shadow',
    $value: '0 2px 12px 0 hsla(228 6% 10% / 0.12)',
    $description: 'Medium elevation for dropdowns',
  } satisfies ShadowToken,

  /** Level 3: High elevation */
  depth03: {
    $type: 'shadow',
    $value: '0 0 6px 1px hsla(228 6% 10% / 0.05), 0 2px 24px 0 hsla(228 6% 10% / 0.08)',
    $description: 'High elevation for popovers and toasts',
  } satisfies ShadowToken,

  /** Level 4: Maximum elevation */
  depth04: {
    $type: 'shadow',
    $value: '0 4px 32px 0 hsla(228 6% 10% / 0.2), 0 16px 48px 0 hsla(228 6% 10% / 0.15)',
    $description: 'Maximum elevation for modals',
  } satisfies ShadowToken,
} as const;

/**
 * Interactive shadow tokens
 * For buttons and interactive elements
 */
export const shadowInteractive = {
  /** Resting state shadow */
  resting: {
    $type: 'shadow',
    $value: '0 1px 2px 0 hsla(228 6% 10% / 0.05)',
    $description: 'Subtle resting shadow',
  } satisfies ShadowToken,

  /** Hovered/lifted state */
  lifted: {
    $type: 'shadow',
    $value: '0 2px 8px 0 hsla(228 6% 10% / 0.08)',
    $description: 'Lifted shadow on hover',
  } satisfies ShadowToken,

  /** Pressed/inset state */
  pressed: {
    $type: 'shadow',
    $value: 'inset 0 2px 0 0 hsla(228 6% 12% / 0.05)',
    $description: 'Inset shadow when pressed',
  } satisfies ShadowToken,
} as const;

/**
 * Focus ring tokens
 * Accessibility-compliant focus indicators
 */
export const focusRing = {
  /** Default focus ring */
  default: {
    $type: 'shadow',
    $value: '0 0 0 2px hsla(235 56% 60% / 0.3)',
    $description: 'Default focus ring',
  } satisfies ShadowToken,

  /** Focus ring with offset */
  offset: {
    $type: 'shadow',
    $value: '0 0 0 4px hsla(235 56% 60% / 0.1)',
    $description: 'Focus ring with offset',
  } satisfies ShadowToken,

  /** Combined focus ring (ring + offset) */
  combined: {
    $type: 'shadow',
    $value: '0 0 0 2px hsla(235 56% 60% / 0.3), 0 0 0 4px hsla(235 56% 60% / 0.1)',
    $description: 'Combined focus ring with offset',
  } satisfies ShadowToken,

  /** Error state focus ring */
  error: {
    $type: 'shadow',
    $value: '0 0 0 2px hsla(0 72% 52% / 0.3)',
    $description: 'Focus ring for error state',
  } satisfies ShadowToken,

  /** Success state focus ring */
  success: {
    $type: 'shadow',
    $value: '0 0 0 2px hsla(142 55% 50% / 0.3)',
    $description: 'Focus ring for success state',
  } satisfies ShadowToken,

  /** Inset focus ring (for inputs) */
  inset: {
    $type: 'shadow',
    $value: 'inset 0 0 0 1px hsla(235 56% 60% / 0.5)',
    $description: 'Inset focus indicator',
  } satisfies ShadowToken,
} as const;

/**
 * Component-specific shadows
 */
export const shadowComponent = {
  /** Modal shadow */
  modal: shadowDepth.depth04,

  /** Popover shadow */
  popover: shadowDepth.depth03,

  /** Dropdown shadow */
  dropdown: shadowDepth.depth02,

  /** Card shadow */
  card: shadowDepth.depth01,

  /** Toast/notification shadow */
  toast: {
    $type: 'shadow',
    $value: '0 4px 12px 0 hsla(228 6% 10% / 0.15), 0 0 1px 0 hsla(228 6% 10% / 0.1)',
    $description: 'Toast notification shadow',
  } satisfies ShadowToken,

  /** Tooltip shadow */
  tooltip: {
    $type: 'shadow',
    $value: '0 2px 8px 0 hsla(228 6% 10% / 0.15)',
    $description: 'Tooltip shadow',
  } satisfies ShadowToken,

  /** Floating action button shadow */
  fab: {
    $type: 'shadow',
    $value: '0 4px 16px 0 hsla(228 6% 10% / 0.2)',
    $description: 'Floating action button shadow',
  } satisfies ShadowToken,

  /** Sticky header shadow */
  stickyHeader: {
    $type: 'shadow',
    $value: '0 1px 3px 0 hsla(228 6% 10% / 0.1)',
    $description: 'Sticky header shadow',
  } satisfies ShadowToken,
} as const;

/**
 * Glow effects (for special states)
 */
export const glowEffects = {
  /** Accent glow */
  accent: {
    $type: 'shadow',
    $value: '0 0 20px 0 hsla(235 56% 60% / 0.3)',
    $description: 'Accent color glow',
  } satisfies ShadowToken,

  /** Smart/AI glow */
  smart: {
    $type: 'shadow',
    $value: '0 0 20px 0 hsla(256 94% 60% / 0.3)',
    $description: 'Smart/AI feature glow',
  } satisfies ShadowToken,

  /** Success glow */
  success: {
    $type: 'shadow',
    $value: '0 0 20px 0 hsla(142 55% 50% / 0.3)',
    $description: 'Success state glow',
  } satisfies ShadowToken,

  /** Error glow */
  error: {
    $type: 'shadow',
    $value: '0 0 20px 0 hsla(0 72% 50% / 0.3)',
    $description: 'Error state glow',
  } satisfies ShadowToken,
} as const;

/**
 * Combined effect semantic tokens
 */
export const effectTokens = {
  shadow: {
    depth: shadowDepth,
    interactive: shadowInteractive,
    component: shadowComponent,
  },
  focus: focusRing,
  glow: glowEffects,
} as const;

/**
 * Helper to get shadow CSS value
 */
export function getShadowValue(
  category: 'depth' | 'interactive' | 'component',
  key: string,
): string | undefined {
  const categoryObj = effectTokens.shadow[category];
  if (categoryObj && key in categoryObj) {
    return (categoryObj as Record<string, ShadowToken>)[key]?.$value;
  }
  return undefined;
}

/**
 * Type exports
 */
export type ShadowDepthKey = keyof typeof shadowDepth;
export type ShadowInteractiveKey = keyof typeof shadowInteractive;
export type FocusRingKey = keyof typeof focusRing;
