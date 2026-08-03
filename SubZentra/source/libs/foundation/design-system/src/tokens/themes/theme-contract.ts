/**
 * Theme Contract - Tier 3
 * Defines the structure all themes must implement
 * Enables type-safe multi-brand/white-label support
 *
 * @module tokens/themes/theme-contract
 */

/**
 * Interactive state interface
 * Used for buttons, links, and other interactive elements
 */
export interface InteractiveState {
  readonly resting: string;
  readonly hovered: string;
  readonly pressed: string;
  readonly disabled?: string;
}

/**
 * Theme mode indicator
 */
export type ThemeMode = 'light' | 'dark';

/**
 * Theme Contract Interface
 *
 * All themes must implement this interface to ensure
 * consistency and enable type-safe theme switching.
 *
 * Structure:
 * - name: Human-readable theme name
 * - mode: 'light' | 'dark'
 * - colors: All color tokens organized by purpose
 * - effects: Shadows and focus indicators
 */
export interface ThemeContract {
  /** Theme identifier/name */
  readonly name: string;

  /** Theme mode (light/dark) */
  readonly mode: ThemeMode;

  /** Color tokens */
  readonly colors: {
    /** Background layer hierarchy */
    readonly background: {
      /** Deepest background (canvas) */
      readonly layer00: string;
      /** Default surface (cards, panels) */
      readonly layer01: string;
      /** Elevated surface (dropdowns, popovers) */
      readonly layer02: string;
      /** Highest elevation (modals, dialogs) */
      readonly layer03: string;
      /** Backdrop overlay */
      readonly overlay: string;
    };

    /** Text color hierarchy */
    readonly text: {
      /** Maximum emphasis - headings */
      readonly highlight: string;
      /** Primary text - default content */
      readonly primary: string;
      /** Secondary text - reduced emphasis */
      readonly secondary: string;
      /** Tertiary text - placeholders */
      readonly tertiary: string;
      /** Muted text - disabled states */
      readonly muted: string;
      /** Inverted text - on colored backgrounds */
      readonly inverted: string;
    };

    /** Interactive element states */
    readonly interactive: {
      /** Primary action */
      readonly primary: InteractiveState;
      /** Secondary action */
      readonly secondary: InteractiveState;
      /** Tertiary/ghost action */
      readonly tertiary: InteractiveState;
      /** Destructive action */
      readonly destructive: InteractiveState;
      /** Smart/AI action */
      readonly smart: InteractiveState;
    };

    /** Border colors */
    readonly border: {
      /** Default border */
      readonly default: string;
      /** Subtle border */
      readonly subtle: string;
      /** Emphasized border */
      readonly emphasis: string;
      /** Focus indicator */
      readonly focus: string;
    };

    /** Feedback/status colors */
    readonly feedback: {
      readonly success: string;
      readonly warning: string;
      readonly error: string;
      readonly info: string;
    };
  };

  /** Effect tokens (shadows, focus rings) */
  readonly effects: {
    /** Shadow depth levels */
    readonly shadow: {
      /** Subtle lift */
      readonly depth01: string;
      /** Medium elevation */
      readonly depth02: string;
      /** High elevation */
      readonly depth03: string;
      /** Maximum elevation */
      readonly depth04: string;
    };

    /** Focus indicators */
    readonly focus: {
      /** Default focus ring */
      readonly ring: string;
      /** Focus ring with offset */
      readonly ringOffset: string;
    };
  };
}

/**
 * Type helper for extracting all theme token paths
 * Useful for type-safe token access
 */
export type ThemeTokenPath =
  | `colors.background.${keyof ThemeContract['colors']['background']}`
  | `colors.text.${keyof ThemeContract['colors']['text']}`
  | `colors.interactive.${keyof ThemeContract['colors']['interactive']}.${keyof InteractiveState}`
  | `colors.border.${keyof ThemeContract['colors']['border']}`
  | `colors.feedback.${keyof ThemeContract['colors']['feedback']}`
  | `effects.shadow.${keyof ThemeContract['effects']['shadow']}`
  | `effects.focus.${keyof ThemeContract['effects']['focus']}`;

/**
 * Type helper for background keys
 */
export type BackgroundKey = keyof ThemeContract['colors']['background'];

/**
 * Type helper for text keys
 */
export type TextKey = keyof ThemeContract['colors']['text'];

/**
 * Type helper for interactive variant keys
 */
export type InteractiveVariant = keyof ThemeContract['colors']['interactive'];

/**
 * Type helper for border keys
 */
export type BorderKey = keyof ThemeContract['colors']['border'];

/**
 * Type helper for feedback keys
 */
export type FeedbackKey = keyof ThemeContract['colors']['feedback'];

/**
 * Type helper for shadow keys
 */
export type ShadowKey = keyof ThemeContract['effects']['shadow'];

/**
 * Type helper for focus keys
 */
export type FocusKey = keyof ThemeContract['effects']['focus'];

/**
 * Validates that an object implements the ThemeContract
 * Use at compile time for type safety
 *
 * @param theme - Theme object to validate
 * @returns The same theme object with type assertion
 */
export function createTheme<T extends ThemeContract>(theme: T): T {
  return theme;
}

/**
 * Gets a token value from a theme using a dot-notated path
 *
 * @param theme - Theme object
 * @param path - Dot-notated path to token
 * @returns Token value or undefined
 *
 * @example
 * const bgColor = getThemeToken(darkTheme, 'colors.background.layer01');
 */
export function getThemeToken(
  theme: ThemeContract,
  path: string,
): string | InteractiveState | undefined {
  const parts = path.split('.');
  let current: unknown = theme;

  for (const part of parts) {
    if (current && typeof current === 'object' && part in current) {
      current = (current as Record<string, unknown>)[part];
    } else {
      return undefined;
    }
  }

  return current as string | InteractiveState | undefined;
}

/**
 * Brand configuration for white-label themes
 */
export interface BrandConfig {
  /** Brand name */
  readonly name: string;
  /** Primary brand color (HSL) */
  readonly primaryHue: number;
  readonly primarySaturation: number;
  /** Optional secondary brand color */
  readonly secondaryHue?: number;
  readonly secondarySaturation?: number;
  /** Neutral hue adjustment */
  readonly neutralHue?: number;
}

/**
 * Creates a branded theme by adjusting hue values
 * Useful for white-label implementations
 *
 * @param baseTheme - Base theme to modify
 * @param brand - Brand configuration
 * @returns New theme with brand colors
 */
export function createBrandedTheme(baseTheme: ThemeContract, brand: BrandConfig): ThemeContract {
  // This is a placeholder - actual implementation would
  // modify the HSL values in all relevant tokens
  return {
    ...baseTheme,
    name: `${brand.name} ${baseTheme.mode === 'dark' ? 'Dark' : 'Light'}`,
  };
}
