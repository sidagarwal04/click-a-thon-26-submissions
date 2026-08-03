/**
 * Theme configuration type definitions
 * @module types/theme
 */

import type { ComponentAnalytics } from './component';
import type { ComponentThemeConfigStructure, SlotThemeConfig } from './cva';

/**
 * Design token configuration for runtime overrides
 */
export interface DesignTokens {
  colors?: Record<string, string>;
  spacing?: Record<string, string>;
  radii?: Record<string, string>;
  shadows?: Record<string, string>;
  fontSizes?: Record<string, string>;
  fontWeights?: Record<string, string>;
  lineHeights?: Record<string, string>;
  durations?: Record<string, string>;
  easings?: Record<string, string>;
}

/**
 * Feature flags for component behavior
 */
export interface FeatureFlags {
  [key: string]: boolean;
}

/**
 * Direction for RTL support
 */
export const DIRECTION = {
  LTR: 'ltr',
  RTL: 'rtl',
} as const;

export type Direction = (typeof DIRECTION)[keyof typeof DIRECTION];

/**
 * Components configuration map
 * Each component can have its own theme configuration
 */
export interface ThemeComponents {
  button?: ComponentThemeConfigStructure;
  iconButton?: ComponentThemeConfigStructure;
  input?: ComponentThemeConfigStructure;
  textarea?: ComponentThemeConfigStructure;
  checkbox?: ComponentThemeConfigStructure;
  radioGroup?: ComponentThemeConfigStructure;
  switch?: ComponentThemeConfigStructure;
  select?: ComponentThemeConfigStructure;
  badge?: ComponentThemeConfigStructure;
  tag?: ComponentThemeConfigStructure;
  spinner?: ComponentThemeConfigStructure;
  skeleton?: ComponentThemeConfigStructure;
  progress?: ComponentThemeConfigStructure;
  // Allow extension via module augmentation
  [key: string]: ComponentThemeConfigStructure | undefined;
}

/**
 * Full theme configuration
 */
export interface ThemeConfig {
  /** Override design tokens (CSS variables) at runtime */
  tokens?: DesignTokens;
  /** Component-level theme configurations */
  components: ThemeComponents;
}

/**
 * ThemeProvider props
 */
export interface ThemeProviderProps {
  /** Theme configuration */
  theme: ThemeConfig;
  /** Children to render */
  children: React.ReactNode;
  /** Whether to inherit and merge with parent theme */
  inherit?: boolean;
  /** Analytics configuration for component tracking */
  analytics?: ComponentAnalytics;
  /** Feature flags for conditional rendering */
  featureFlags?: FeatureFlags;
  /** Text direction for RTL support */
  dir?: Direction;
  /** Locale for i18n */
  locale?: string;
  /** Disable the wrapper div (useful when you don't need dir attribute or want to avoid extra DOM node) */
  disableWrapper?: boolean;
}

/**
 * Theme context value
 */
export interface ThemeContextValue {
  /** Current theme configuration */
  theme: ThemeConfig;
  /** Analytics hooks */
  analytics?: ComponentAnalytics;
  /** Feature flags */
  featureFlags?: FeatureFlags;
  /** Text direction */
  dir: Direction;
  /** Locale */
  locale?: string;
  /** Get component theme config */
  getComponentTheme: <K extends keyof ThemeComponents>(
    componentName: K,
  ) => ThemeComponents[K] | undefined;
  /** Check if a feature flag is enabled */
  isFeatureEnabled: (flagName: string) => boolean;
}

/**
 * Re-export SlotThemeConfig for convenience
 */
export type { SlotThemeConfig, ComponentThemeConfigStructure };

/**
 * Theme component prop for declaring component theme in module augmentation
 */
export type ComponentThemeProp<T> = T extends ComponentThemeConfigStructure ? T : never;

/**
 * Default component themes that can be extended
 */
export interface DefaultComponentThemes {
  button: ComponentThemeConfigStructure;
  iconButton: ComponentThemeConfigStructure;
  input: ComponentThemeConfigStructure;
  textarea: ComponentThemeConfigStructure;
  checkbox: ComponentThemeConfigStructure;
  radioGroup: ComponentThemeConfigStructure;
  switch: ComponentThemeConfigStructure;
  select: ComponentThemeConfigStructure;
  badge: ComponentThemeConfigStructure;
  tag: ComponentThemeConfigStructure;
  spinner: ComponentThemeConfigStructure;
  skeleton: ComponentThemeConfigStructure;
  progress: ComponentThemeConfigStructure;
}

/**
 * Hook return type for useTheme
 */
export interface UseThemeReturn {
  root: (props: Record<string, unknown>) => string;
  [slotName: string]: (props: Record<string, unknown>) => string;
}
