/**
 * CVA (Class Variance Authority) type definitions
 * Adapted from: https://github.com/joe-bell/cva
 * @module types/cva
 */

export const CLASS_PROP_KEY = {
  CLASS: 'class',
  CLASS_NAME: 'className',
} as const;

export type ClassPropKey = (typeof CLASS_PROP_KEY)[keyof typeof CLASS_PROP_KEY];

const BOOLEAN_STRING_LITERAL = {
  TRUE: 'true',
  FALSE: 'false',
} as const;

type BooleanStringLiteral = (typeof BOOLEAN_STRING_LITERAL)[keyof typeof BOOLEAN_STRING_LITERAL];

export type ClassValue = string | null | undefined | ClassValue[];

export type ClassProp =
  | {
      class: ClassValue;
      className?: never;
    }
  | { class?: never; className: ClassValue }
  | { class?: never; className?: never };

export type OmitUndefined<T> = T extends undefined ? never : T;
export type StringToBoolean<T> = T extends BooleanStringLiteral ? boolean : T;

export type ConfigSchema = Record<string, Record<string, ClassValue>>;

export type ConfigVariants<T extends ConfigSchema> = {
  [Variant in keyof T]?: StringToBoolean<keyof T[Variant]> | null;
};

export type ConfigVariantsMulti<T extends ConfigSchema> = {
  [Variant in keyof T]?: StringToBoolean<keyof T[Variant]> | StringToBoolean<keyof T[Variant]>[];
};

export type ComponentThemeConfig<T> = T extends ConfigSchema
  ? {
      variants?: T;
      defaultVariants?: ConfigVariants<T>;
      compoundVariants?: (T extends ConfigSchema
        ? (ConfigVariants<T> | ConfigVariantsMulti<T>) & ClassProp
        : ClassProp)[];
    }
  : never;

export type CvaProps<T> = T extends ConfigSchema ? ConfigVariants<T> & ClassProp : ClassProp;

/**
 * Slot theme configuration for a single slot
 */
export interface SlotThemeConfig {
  /** Base classes always applied */
  base?: string;
  /** Classes per variant value */
  variants?: {
    [variantName: string]: {
      [variantValue: string]: string;
    };
  };
  /** Classes for boolean modifiers */
  modifiers?: {
    [modifierName: string]: {
      true: string;
      false?: string;
    };
  };
  /** Compound variants - classes applied when multiple conditions match */
  compoundVariants?: Array<{
    [key: string]: string | boolean;
    className: string;
  }>;
}

/**
 * Component theme configuration structure
 */
export interface ComponentThemeConfigStructure {
  /** Root element styling */
  root: SlotThemeConfig;
  /** Named slots styling */
  slots?: {
    [slotName: string]: SlotThemeConfig;
  };
  /** Default variant values */
  defaultVariants?: {
    [variantName: string]: string;
  };
}
