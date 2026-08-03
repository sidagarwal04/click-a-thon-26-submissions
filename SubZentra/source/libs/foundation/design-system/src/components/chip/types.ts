/**
 * Chip component type definitions
 * @module components/chip/types
 */

import type {
  ComponentThemeConfigStructure,
  OIComponentOwnProps,
  OIComponentSlotProps,
  PolymorphicProps,
  PolymorphicRef,
} from '../../types';

/**
 * Chip variant definitions
 */
export const ChipVariants = {
  variant: ['default', 'primary', 'success', 'warning', 'error', 'info'] as const,
  size: ['sm', 'md', 'lg'] as const,
} as const;

/**
 * Chip modifier definitions
 */
export const ChipModifiers = ['removable', 'rounded', 'disabled'] as const;

/**
 * Chip slot definitions
 */
export const ChipSlots = ['start', 'close'] as const;

/**
 * Chip's own props
 */
export interface ChipOwnProps
  extends OIComponentOwnProps<typeof ChipVariants, typeof ChipModifiers, typeof ChipSlots> {
  /** Visual variant */
  variant?: (typeof ChipVariants.variant)[number];
  /** Size of the chip */
  size?: (typeof ChipVariants.size)[number];
  /** Whether the chip can be removed */
  removable?: boolean;
  /** Use fully rounded corners */
  rounded?: boolean;
  /** Disabled state */
  disabled?: boolean;
  /** Content at the start of the chip */
  start?: OIComponentSlotProps;
  /** Custom close button content */
  close?: OIComponentSlotProps;
  /** Callback when remove button is clicked */
  onRemove?: () => void;
  /** Chip content */
  children?: React.ReactNode;
}

/**
 * Chip component props
 */
export type ChipProps<T extends React.ElementType = 'span'> = PolymorphicProps<T, ChipOwnProps>;

/**
 * Chip component ref type
 */
export type ChipRef<T extends React.ElementType = 'span'> = PolymorphicRef<T>;

/**
 * Chip component type
 */
export interface ChipComponent {
  <T extends React.ElementType = 'span'>(
    props: ChipProps<T> & { ref?: ChipRef<T> },
  ): React.ReactNode;
  displayName?: string;
}

/**
 * Default theme configuration for Chip
 */
export const chipDefaultTheme: ComponentThemeConfigStructure = {
  root: {
    base: 'inline-flex items-center gap-1.5 font-medium transition-colors',
    variants: {
      variant: {
        default: 'bg-muted text-muted-foreground',
        primary: 'bg-primary/10 text-primary',
        success: 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400',
        warning: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400',
        error: 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400',
        info: 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400',
      },
      size: {
        sm: 'h-6 px-2 text-xs',
        md: 'h-7 px-2.5 text-sm',
        lg: 'h-8 px-3 text-sm',
      },
    },
    modifiers: {
      removable: {
        true: 'pr-1',
        false: '',
      },
      rounded: {
        true: 'rounded-full',
        false: 'rounded-md',
      },
      disabled: {
        true: 'opacity-50 cursor-not-allowed',
        false: '',
      },
    },
  },
  slots: {
    start: {
      base: 'shrink-0',
      variants: {
        size: {
          sm: '[&>svg]:h-3 [&>svg]:w-3',
          md: '[&>svg]:h-3.5 [&>svg]:w-3.5',
          lg: '[&>svg]:h-4 [&>svg]:w-4',
        },
      },
      modifiers: {},
    },
    close: {
      base: 'shrink-0 rounded-full p-0.5 hover:bg-black/10 dark:hover:bg-white/10 focus:outline-none focus:ring-2 focus:ring-offset-1',
      variants: {
        size: {
          sm: '[&>svg]:h-3 [&>svg]:w-3',
          md: '[&>svg]:h-3.5 [&>svg]:w-3.5',
          lg: '[&>svg]:h-4 [&>svg]:w-4',
        },
      },
      modifiers: {
        disabled: {
          true: 'pointer-events-none',
          false: '',
        },
      },
    },
  },
  defaultVariants: {
    variant: 'default',
    size: 'md',
  },
};
