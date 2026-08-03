/**
 * OpenZentra Design System - Type Definitions
 * @module types
 */

// Utility types
export type {
  FullPartial,
  OmitNever,
  Resolve,
  PropsOf,
  DeepMerge,
  KeysOf,
  RequireKeys,
  OptionalKeys,
  StrictOmit,
  ArrayElement,
  UnionToIntersection,
} from './utils';

// CVA types
export type {
  ClassPropKey,
  ClassValue,
  ClassProp,
  OmitUndefined,
  StringToBoolean,
  ConfigSchema,
  ConfigVariants,
  ConfigVariantsMulti,
  ComponentThemeConfig,
  CvaProps,
  SlotThemeConfig,
  ComponentThemeConfigStructure,
} from './cva';

export { CLASS_PROP_KEY } from './cva';

// Polymorphic types
export type {
  PolymorphicRef,
  PolymorphicComponentProp,
  PolymorphicProps,
  PolymorphicComponent,
  PolymorphicForwardRefComponent,
  OverridableComponentProps,
} from './polymorphic';

// Component types
export type {
  OIDefaultProps,
  OIComponentClassName,
  OIComponentSlotProps,
  OIComponentVariants,
  OIComponentModifiers,
  OIComponentSlotObject,
  OIComponentSlot,
  OIComponentSlots,
  NormalizeSlots,
  OverridableSlots,
  SlotNames,
  OIComponentOwnProps,
  OIComponentThemeConfig,
  GetOIComponentThemeConfig,
  GetSlots,
  OIComponentRef,
  OIComponentProps,
  OIPolymorphicComponent,
  OIPolymorphicForwardRefComponent,
  InteractionEvent,
  ComponentAnalytics,
} from './component';

// Theme types
export type {
  DesignTokens,
  FeatureFlags,
  Direction,
  ThemeComponents,
  ThemeConfig,
  ThemeProviderProps,
  ThemeContextValue,
  ComponentThemeProp,
  DefaultComponentThemes,
  UseThemeReturn,
} from './theme';

export { DIRECTION } from './theme';
