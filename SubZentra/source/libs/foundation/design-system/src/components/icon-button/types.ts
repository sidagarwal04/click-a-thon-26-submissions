/**
 * IconButton component type definitions
 * @module components/icon-button/types
 */

import type {
  ComponentThemeConfigStructure,
  OIDefaultProps,
  PolymorphicProps,
  PolymorphicRef,
} from '../../types';

/**
 * IconButton variant definitions
 */
export const IconButtonVariants = {
  intent: ['primary', 'secondary', 'danger', 'ghost'] as const,
  size: ['sm', 'md', 'lg'] as const,
} as const;

/**
 * IconButton modifier definitions
 */
export const IconButtonModifiers = ['disabled', 'loading'] as const;

/**
 * IconButton slot definitions
 */
export const IconButtonSlots = ['icon'] as const;

/**
 * IconButton's own props (manually defined for better control)
 */
export interface IconButtonOwnProps extends OIDefaultProps {
  /** IconButton intent/style variant */
  intent?: (typeof IconButtonVariants.intent)[number];
  /** IconButton size */
  size?: (typeof IconButtonVariants.size)[number];
  /** Disabled state */
  disabled?: boolean;
  /** Loading state */
  loading?: boolean;
  /**
   * Accessible label for screen readers (REQUIRED for accessibility)
   *
   * Icon buttons have no visible text, so an aria-label is required
   * to describe the button's action to assistive technology users.
   *
   * @example
   * <IconButton aria-label="Close dialog">
   *   <XIcon />
   * </IconButton>
   */
  'aria-label': string;
  /** Children content (icon) */
  children?: React.ReactNode;
}

/**
 * IconButton component props with polymorphism support
 */
export type IconButtonProps<T extends React.ElementType = 'button'> = PolymorphicProps<
  T,
  IconButtonOwnProps
>;

/**
 * IconButton component ref type
 */
export type IconButtonRef<T extends React.ElementType = 'button'> = PolymorphicRef<T>;

/**
 * IconButton component type (polymorphic with forwardRef)
 */
export interface IconButtonComponent {
  <T extends React.ElementType = 'button'>(
    props: IconButtonProps<T> & { ref?: IconButtonRef<T> },
  ): React.ReactNode;
  displayName?: string;
}

/**
 * Default theme configuration for IconButton
 */
export const iconButtonDefaultTheme: ComponentThemeConfigStructure = {
  root: {
    base: 'inline-flex items-center justify-center rounded-md transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 disabled:pointer-events-none',
    variants: {
      intent: {
        primary:
          'bg-primary text-primary-foreground hover:bg-primary-hover focus-visible:ring-primary',
        secondary:
          'bg-secondary text-secondary-foreground hover:bg-secondary-hover focus-visible:ring-secondary border border-border',
        danger: 'bg-danger text-danger-foreground hover:bg-danger-hover focus-visible:ring-danger',
        ghost: 'bg-transparent hover:bg-secondary text-foreground',
      },
      size: {
        sm: 'h-8 w-8',
        md: 'h-10 w-10',
        lg: 'h-12 w-12',
      },
    },
    modifiers: {
      disabled: {
        true: 'opacity-50 cursor-not-allowed',
        false: '',
      },
      loading: {
        true: 'cursor-wait',
        false: '',
      },
    },
  },
  slots: {
    icon: {
      base: 'shrink-0',
      variants: {
        size: {
          sm: 'w-4 h-4',
          md: 'w-5 h-5',
          lg: 'w-6 h-6',
        },
      },
      modifiers: {},
    },
  },
  defaultVariants: {
    intent: 'secondary',
    size: 'md',
  },
};
