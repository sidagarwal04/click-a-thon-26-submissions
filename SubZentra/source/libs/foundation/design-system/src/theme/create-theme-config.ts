/**
 * Factory function for creating type-safe theme configurations
 * @module theme/create-theme-config
 */

import type {
  ComponentThemeConfigStructure,
  OIComponentModifiers,
  OIComponentSlots,
  OIComponentVariants,
  SlotThemeConfig,
} from '../types';

/**
 * Options for creating a theme configuration
 */
export interface CreateThemeConfigOptions<
  Variants extends OIComponentVariants,
  Modifiers extends OIComponentModifiers,
  Slots extends OIComponentSlots,
> {
  /** Component name for identification */
  name: string;
  /** Variant definitions */
  variants: Variants;
  /** Modifier definitions */
  modifiers: Modifiers;
  /** Slot definitions */
  slots: Slots;
  /** Root slot configuration */
  root: SlotThemeConfig;
  /** Named slot configurations */
  slotConfigs?: Partial<
    Record<Slots[number] extends string ? Slots[number] : never, SlotThemeConfig>
  >;
  /** Default variant values */
  defaultVariants?: Partial<{ [K in keyof Variants]: Variants[K][number] }>;
}

/**
 * Creates a type-safe theme configuration for a component
 *
 * @example
 * const buttonThemeConfig = createThemeConfig({
 *   name: 'button',
 *   variants: ButtonVariants,
 *   modifiers: ButtonModifiers,
 *   slots: ButtonSlots,
 *   root: {
 *     base: 'inline-flex items-center justify-center',
 *     variants: {
 *       intent: {
 *         primary: 'bg-primary text-white',
 *         secondary: 'bg-secondary text-foreground',
 *       },
 *       size: {
 *         sm: 'h-8 px-3 text-sm',
 *         md: 'h-10 px-4',
 *         lg: 'h-12 px-6 text-lg',
 *       },
 *     },
 *     modifiers: {
 *       disabled: { true: 'opacity-50 cursor-not-allowed', false: '' },
 *       loading: { true: 'cursor-wait', false: '' },
 *     },
 *   },
 *   slotConfigs: {
 *     startIcon: {
 *       base: 'shrink-0',
 *       variants: { size: { sm: 'w-4 h-4', md: 'w-5 h-5', lg: 'w-6 h-6' } },
 *     },
 *   },
 *   defaultVariants: {
 *     intent: 'primary',
 *     size: 'md',
 *   },
 * });
 *
 * @param options - Theme configuration options
 * @returns Component theme configuration structure
 */
export function createThemeConfig<
  Variants extends OIComponentVariants,
  Modifiers extends OIComponentModifiers,
  Slots extends OIComponentSlots,
>(options: CreateThemeConfigOptions<Variants, Modifiers, Slots>): ComponentThemeConfigStructure {
  const { root, slotConfigs, defaultVariants } = options;

  // Convert slot configs to the expected format
  const slots: Record<string, SlotThemeConfig> | undefined = slotConfigs
    ? Object.entries(slotConfigs).reduce((acc, [slotName, config]) => {
        if (config) {
          acc[slotName] = config;
        }
        return acc;
      }, {} as Record<string, SlotThemeConfig>)
    : undefined;

  return {
    root,
    slots,
    defaultVariants: defaultVariants as Record<string, string> | undefined,
  };
}

/**
 * Creates an empty slot configuration
 * Useful as a starting point for slot configurations
 */
export function createEmptySlotConfig(): SlotThemeConfig {
  return {
    base: '',
    variants: {},
    modifiers: {},
  };
}

/**
 * Helper to create variant configuration
 *
 * @example
 * const sizeVariants = createVariantConfig({
 *   sm: 'text-sm p-2',
 *   md: 'text-base p-3',
 *   lg: 'text-lg p-4',
 * });
 */
export function createVariantConfig<T extends Record<string, string>>(config: T): T {
  return config;
}

/**
 * Helper to create modifier configuration
 *
 * @example
 * const disabledModifier = createModifierConfig({
 *   true: 'opacity-50 cursor-not-allowed',
 *   false: '',
 * });
 */
export function createModifierConfig(config: { true: string; false?: string }): {
  true: string;
  false?: string;
} {
  return config;
}
