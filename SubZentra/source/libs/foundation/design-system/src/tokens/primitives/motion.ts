/**
 * Motion Primitives - Tier 1 Tokens
 * Duration, easing, and animation tokens
 *
 * Accessibility-first approach:
 * - All durations can be disabled via prefers-reduced-motion
 * - Easing functions are designed for comfortable transitions
 * - No disorienting animations
 *
 * @module tokens/primitives/motion
 */

import type { CubicBezierToken, DesignToken, DurationToken } from '../types';

/**
 * Duration tokens for animations and transitions
 *
 * Usage guidelines:
 * - instant: State changes that should feel immediate
 * - fast: Micro-interactions (button press, hover)
 * - normal: Standard UI transitions (dropdowns, tabs)
 * - slow: Complex animations (modals, drawers)
 * - slower: Deliberate, attention-grabbing animations
 */
export const durations = {
  instant: {
    $type: 'duration',
    $value: '0ms',
    $ms: 0,
    $description: 'Instant feedback, no visible transition',
  },
  fast: {
    $type: 'duration',
    $value: '100ms',
    $ms: 100,
    $description: 'Quick micro-interactions',
  },
  normal: {
    $type: 'duration',
    $value: '200ms',
    $ms: 200,
    $description: 'Standard UI transitions',
  },
  slow: {
    $type: 'duration',
    $value: '300ms',
    $ms: 300,
    $description: 'Complex animations',
  },
  slower: {
    $type: 'duration',
    $value: '500ms',
    $ms: 500,
    $description: 'Deliberate emphasis animations',
  },
} as const satisfies Record<string, DurationToken>;

/**
 * Easing functions for animations
 *
 * Easing philosophy:
 * - linear: Constant speed, use sparingly
 * - easeIn: Starts slow, accelerates (exits)
 * - easeOut: Starts fast, decelerates (entrances)
 * - easeInOut: Smooth start and end (general purpose)
 * - spring: Playful bounce effect (confirmations)
 */
export const easings = {
  linear: {
    $type: 'cubicBezier',
    $value: 'linear',
    $description: 'Constant speed, no acceleration',
  },
  easeIn: {
    $type: 'cubicBezier',
    $value: 'cubic-bezier(0.4, 0, 1, 1)',
    $points: [0.4, 0, 1, 1],
    $description: 'Accelerating motion, good for exits',
  },
  easeOut: {
    $type: 'cubicBezier',
    $value: 'cubic-bezier(0, 0, 0.2, 1)',
    $points: [0, 0, 0.2, 1],
    $description: 'Decelerating motion, good for entrances',
  },
  easeInOut: {
    $type: 'cubicBezier',
    $value: 'cubic-bezier(0.4, 0, 0.2, 1)',
    $points: [0.4, 0, 0.2, 1],
    $description: 'Smooth acceleration and deceleration',
  },
  spring: {
    $type: 'cubicBezier',
    $value: 'cubic-bezier(0.68, -0.55, 0.265, 1.55)',
    $points: [0.68, -0.55, 0.265, 1.55],
    $description: 'Playful bounce effect',
  },
  emphasize: {
    $type: 'cubicBezier',
    $value: 'cubic-bezier(0.2, 0, 0, 1)',
    $points: [0.2, 0, 0, 1],
    $description: 'Strong deceleration for emphasis',
  },
} as const satisfies Record<string, CubicBezierToken>;

/**
 * Transition presets combining duration and easing
 * Ready-to-use transition values
 */
export const transitions = {
  /** Fast hover effects */
  hover: {
    $type: 'transition' as const,
    $value: '100ms cubic-bezier(0, 0, 0.2, 1)',
    $description: 'Quick hover state transition',
  },
  /** Standard color changes */
  color: {
    $type: 'transition' as const,
    $value: '200ms cubic-bezier(0.4, 0, 0.2, 1)',
    $description: 'Color transition',
  },
  /** Background changes */
  background: {
    $type: 'transition' as const,
    $value: '200ms cubic-bezier(0.4, 0, 0.2, 1)',
    $description: 'Background transition',
  },
  /** Transform animations */
  transform: {
    $type: 'transition' as const,
    $value: '200ms cubic-bezier(0, 0, 0.2, 1)',
    $description: 'Transform transition',
  },
  /** Opacity changes */
  opacity: {
    $type: 'transition' as const,
    $value: '200ms cubic-bezier(0.4, 0, 0.2, 1)',
    $description: 'Opacity transition',
  },
  /** Size/dimension changes */
  size: {
    $type: 'transition' as const,
    $value: '300ms cubic-bezier(0.4, 0, 0.2, 1)',
    $description: 'Size/dimension transition',
  },
  /** Shadow changes */
  shadow: {
    $type: 'transition' as const,
    $value: '200ms cubic-bezier(0.4, 0, 0.2, 1)',
    $description: 'Shadow transition',
  },
  /** All properties */
  all: {
    $type: 'transition' as const,
    $value: '200ms cubic-bezier(0.4, 0, 0.2, 1)',
    $description: 'General purpose transition',
  },
} as const satisfies Record<string, DesignToken<string>>;

/**
 * Animation keyframe definitions (as CSS strings)
 * These are the animation names and can be used with @keyframes
 */
export const animations = {
  /** Fade in animation */
  fadeIn: {
    $type: 'transition' as const,
    $value: 'fadeIn 200ms cubic-bezier(0, 0, 0.2, 1)',
    $description: 'Fade in from transparent',
  },
  /** Fade out animation */
  fadeOut: {
    $type: 'transition' as const,
    $value: 'fadeOut 200ms cubic-bezier(0.4, 0, 1, 1)',
    $description: 'Fade out to transparent',
  },
  /** Slide in from top */
  slideInFromTop: {
    $type: 'transition' as const,
    $value: 'slideInFromTop 300ms cubic-bezier(0, 0, 0.2, 1)',
    $description: 'Slide in from top',
  },
  /** Slide in from bottom */
  slideInFromBottom: {
    $type: 'transition' as const,
    $value: 'slideInFromBottom 300ms cubic-bezier(0, 0, 0.2, 1)',
    $description: 'Slide in from bottom',
  },
  /** Scale in animation */
  scaleIn: {
    $type: 'transition' as const,
    $value: 'scaleIn 200ms cubic-bezier(0, 0, 0.2, 1)',
    $description: 'Scale in from smaller size',
  },
  /** Spin animation */
  spin: {
    $type: 'transition' as const,
    $value: 'spin 1000ms linear infinite',
    $description: 'Continuous spinning (for loaders)',
  },
  /** Pulse animation */
  pulse: {
    $type: 'transition' as const,
    $value: 'pulse 2000ms cubic-bezier(0.4, 0, 0.6, 1) infinite',
    $description: 'Gentle pulse effect',
  },
} as const satisfies Record<string, DesignToken<string>>;

/**
 * Type for duration keys
 */
export type DurationKey = keyof typeof durations;

/**
 * Type for easing keys
 */
export type EasingKey = keyof typeof easings;

/**
 * Type for transition keys
 */
export type TransitionKey = keyof typeof transitions;

/**
 * Type for animation keys
 */
export type AnimationKey = keyof typeof animations;

/**
 * Combined motion primitives export
 */
export const motionPrimitives = {
  durations,
  easings,
  transitions,
  animations,
} as const;

/**
 * Helper to get CSS variable for duration
 */
export function durationVar(key: DurationKey): string {
  return `var(--duration-${key})`;
}

/**
 * Helper to get CSS variable for easing
 */
export function easingVar(key: EasingKey): string {
  return `var(--ease-${key})`;
}

/**
 * Helper to create a transition string
 */
export function createTransition(
  property: string,
  duration: DurationKey = 'normal',
  easing: EasingKey = 'easeInOut',
): string {
  return `${property} var(--duration-${duration}) var(--ease-${easing})`;
}

/**
 * Creates multiple transitions in one string
 */
export function createTransitions(
  properties: string[],
  duration: DurationKey = 'normal',
  easing: EasingKey = 'easeInOut',
): string {
  return properties.map((prop) => createTransition(prop, duration, easing)).join(', ');
}
