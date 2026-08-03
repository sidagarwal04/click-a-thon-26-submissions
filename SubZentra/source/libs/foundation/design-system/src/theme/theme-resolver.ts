/**
 * Theme class resolver - resolves classes based on variants, modifiers, and theme config
 * @module theme/theme-resolver
 */

import type { ComponentThemeConfigStructure, SlotThemeConfig } from '../types';
import { cn } from '../utils/cn';

/**
 * Props that can be passed to a slot resolver
 */
export interface SlotResolverProps {
  className?: string;
  [key: string]: unknown;
}

/**
 * Creates a class resolver function for a slot
 *
 * @param slotConfig - Slot theme configuration
 * @returns Function that resolves classes based on props
 */
export function createSlotResolver(
  slotConfig: SlotThemeConfig,
): (props: SlotResolverProps) => string {
  return (props: SlotResolverProps): string => {
    const classes: string[] = [];

    // 1. Add base classes
    if (slotConfig.base) {
      classes.push(slotConfig.base);
    }

    // 2. Add variant classes
    if (slotConfig.variants) {
      for (const [variantName, variantValues] of Object.entries(slotConfig.variants)) {
        const value = props[variantName];
        if (value !== undefined && value !== null && typeof value === 'string') {
          const variantClass = variantValues[value];
          if (variantClass) {
            classes.push(variantClass);
          }
        }
      }
    }

    // 3. Add modifier classes
    if (slotConfig.modifiers) {
      for (const [modifierName, modifierConfig] of Object.entries(slotConfig.modifiers)) {
        const value = props[modifierName];
        if (typeof value === 'boolean') {
          const modifierClass = value ? modifierConfig.true : modifierConfig.false;
          if (modifierClass) {
            classes.push(modifierClass);
          }
        }
      }
    }

    // 4. Add compound variant classes
    if (slotConfig.compoundVariants) {
      for (const compound of slotConfig.compoundVariants) {
        const { className: compoundClassName, ...conditions } = compound;
        const matches = Object.entries(conditions).every(([key, value]) => props[key] === value);
        if (matches && typeof compoundClassName === 'string') {
          classes.push(compoundClassName);
        }
      }
    }

    // 5. Add user className (always wins via tailwind-merge)
    if (props.className) {
      classes.push(props.className);
    }

    return cn(...classes);
  };
}

/**
 * Creates resolvers for all slots in a component theme config
 *
 * @param config - Component theme configuration
 * @returns Object with resolver functions for root and all slots
 */
export function createComponentResolvers(
  config: ComponentThemeConfigStructure,
): Record<string, (props: SlotResolverProps) => string> {
  const resolvers: Record<string, (props: SlotResolverProps) => string> = {
    root: createSlotResolver(config.root),
  };

  if (config.slots) {
    for (const [slotName, slotConfig] of Object.entries(config.slots)) {
      resolvers[slotName] = createSlotResolver(slotConfig);
    }
  }

  return resolvers;
}

/**
 * Deep merges two theme configurations
 * User config takes precedence over default config
 *
 * @param defaultConfig - Default theme configuration
 * @param userConfig - User theme configuration (overrides)
 * @returns Merged configuration
 */
export function mergeThemeConfigs(
  defaultConfig: ComponentThemeConfigStructure,
  userConfig?: Partial<ComponentThemeConfigStructure>,
): ComponentThemeConfigStructure {
  if (!userConfig) {
    return defaultConfig;
  }

  return {
    root: mergeSlotConfigs(defaultConfig.root, userConfig.root),
    slots: mergeSlotMap(defaultConfig.slots, userConfig.slots),
    defaultVariants: {
      ...defaultConfig.defaultVariants,
      ...userConfig.defaultVariants,
    },
  };
}

/**
 * Merges two slot configurations
 */
function mergeSlotConfigs(
  defaultSlot: SlotThemeConfig,
  userSlot?: Partial<SlotThemeConfig>,
): SlotThemeConfig {
  if (!userSlot) {
    return defaultSlot;
  }

  return {
    base: userSlot.base ?? defaultSlot.base,
    variants: mergeVariants(defaultSlot.variants, userSlot.variants),
    modifiers: mergeModifiers(defaultSlot.modifiers, userSlot.modifiers),
    compoundVariants: userSlot.compoundVariants ?? defaultSlot.compoundVariants,
  };
}

/**
 * Merges slot maps
 */
function mergeSlotMap(
  defaultSlots?: Record<string, SlotThemeConfig>,
  userSlots?: Record<string, SlotThemeConfig>,
): Record<string, SlotThemeConfig> | undefined {
  if (!defaultSlots && !userSlots) {
    return undefined;
  }

  const merged: Record<string, SlotThemeConfig> = {};
  const allSlotNames = new Set([
    ...Object.keys(defaultSlots || {}),
    ...Object.keys(userSlots || {}),
  ]);

  for (const slotName of allSlotNames) {
    const defaultSlot = defaultSlots?.[slotName];
    const userSlot = userSlots?.[slotName];

    if (defaultSlot && userSlot) {
      merged[slotName] = mergeSlotConfigs(defaultSlot, userSlot);
    } else if (userSlot) {
      merged[slotName] = userSlot;
    } else if (defaultSlot) {
      merged[slotName] = defaultSlot;
    }
  }

  return merged;
}

/**
 * Merges variant configurations
 */
function mergeVariants(
  defaultVariants?: Record<string, Record<string, string>>,
  userVariants?: Record<string, Record<string, string>>,
): Record<string, Record<string, string>> | undefined {
  if (!defaultVariants && !userVariants) {
    return undefined;
  }

  const merged: Record<string, Record<string, string>> = {};
  const allVariantNames = new Set([
    ...Object.keys(defaultVariants || {}),
    ...Object.keys(userVariants || {}),
  ]);

  for (const variantName of allVariantNames) {
    merged[variantName] = {
      ...defaultVariants?.[variantName],
      ...userVariants?.[variantName],
    };
  }

  return merged;
}

/**
 * Merges modifier configurations
 */
function mergeModifiers(
  defaultModifiers?: Record<string, { true: string; false?: string }>,
  userModifiers?: Record<string, { true: string; false?: string }>,
): Record<string, { true: string; false?: string }> | undefined {
  if (!defaultModifiers && !userModifiers) {
    return undefined;
  }

  return {
    ...defaultModifiers,
    ...userModifiers,
  };
}
