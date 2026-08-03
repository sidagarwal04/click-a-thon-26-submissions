/**
 * Open Zentra Design System - Token System
 *
 * Enterprise-grade, W3C-compliant design tokens
 * Following Linear's design language
 *
 * Architecture:
 * - Tier 1 (Primitives): Raw values
 * - Tier 2 (Semantic): Usage-based tokens
 * - Tier 3 (Themes): Theme compositions
 *
 * @module tokens
 */

// =============================================================================
// TYPES
// =============================================================================
export * from './types';

// =============================================================================
// UTILITIES
// =============================================================================
export * from './utils';

// =============================================================================
// TIER 1: PRIMITIVES
// =============================================================================
export * from './primitives';

// =============================================================================
// TIER 2: SEMANTIC
// =============================================================================
export * from './semantic';

// =============================================================================
// TIER 3: THEMES
// =============================================================================
export * from './themes';

// =============================================================================
// CONVENIENCE RE-EXPORTS
// =============================================================================

// Re-export commonly used items at top level for convenience
export { colorPrimitives } from './primitives/colors';
export { typographyPrimitives } from './primitives/typography';
export { spacingPrimitives, radiusPrimitives } from './primitives/spacing';
export { motionPrimitives } from './primitives/motion';

export { backgroundTokens } from './semantic/backgrounds';
export { borderTokens } from './semantic/borders';
export { textTokens } from './semantic/text';
export { effectTokens } from './semantic/effects';

export { darkTheme, lightTheme, defaultTheme, themes, getTheme } from './themes';
