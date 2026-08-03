/**
 * Button component type definitions
 * @module components/button/types
 */

import type {
  ComponentThemeConfigStructure,
  OIComponentSlotProps,
  OIDefaultProps,
  PolymorphicProps,
  PolymorphicRef,
} from '../../types';

/**
 * Button variant definitions
 */
export const ButtonVariants = {
  intent: ['primary', 'secondary', 'danger', 'ghost', 'link'] as const,
  size: ['sm', 'md', 'lg'] as const,
} as const;

/**
 * Button modifier definitions
 */
export const ButtonModifiers = ['disabled', 'loading', 'fullWidth'] as const;

/**
 * Button slot definitions
 */
export const ButtonSlots = ['start', 'end', 'loadingIndicator'] as const;

/**
 * Button's own props (manually defined for better control)
 */
export interface ButtonOwnProps extends OIDefaultProps {
  /** Button intent/style variant */
  intent?: (typeof ButtonVariants.intent)[number];
  /** Button size */
  size?: (typeof ButtonVariants.size)[number];
  /** Disabled state */
  disabled?: boolean;
  /** Loading state */
  loading?: boolean;
  /** Full width button */
  fullWidth?: boolean;
  /** Start slot (icon or content before text) */
  start?: OIComponentSlotProps;
  /** End slot (icon or content after text) */
  end?: OIComponentSlotProps;
  /** Custom loading indicator */
  loadingIndicator?: OIComponentSlotProps;
  /** Accessible label (required for icon-only buttons) */
  'aria-label'?: string;
  /** Children content */
  children?: React.ReactNode;
}

/**
 * Button component props with polymorphism support
 */
export type ButtonProps<T extends React.ElementType = 'button'> = PolymorphicProps<
  T,
  ButtonOwnProps
>;

/**
 * Button component ref type
 */
export type ButtonRef<T extends React.ElementType = 'button'> = PolymorphicRef<T>;

/**
 * Button component type (polymorphic with forwardRef)
 */
export interface ButtonComponent {
  <T extends React.ElementType = 'button'>(
    props: ButtonProps<T> & { ref?: ButtonRef<T> },
  ): React.ReactNode;
  displayName?: string;
}

/**
 * Default theme configuration for Button
 */
export const buttonDefaultTheme: ComponentThemeConfigStructure = {
  root: {
    base: 'inline-flex items-center justify-center font-medium rounded-md transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 disabled:pointer-events-none',
    variants: {
      intent: {
        primary:
          'bg-primary text-primary-foreground hover:bg-primary-hover focus-visible:ring-primary',
        secondary:
          'bg-secondary text-secondary-foreground hover:bg-secondary-hover focus-visible:ring-secondary border border-border',
        danger: 'bg-danger text-danger-foreground hover:bg-danger-hover focus-visible:ring-danger',
        ghost: 'bg-transparent hover:bg-secondary text-foreground',
        link: 'bg-transparent text-primary underline-offset-4 hover:underline p-0 h-auto',
      },
      size: {
        sm: 'h-8 px-3 text-sm gap-1.5',
        md: 'h-10 px-4 text-base gap-2',
        lg: 'h-12 px-6 text-lg gap-2.5',
      },
    },
    modifiers: {
      disabled: {
        true: 'opacity-50 cursor-not-allowed',
        false: '',
      },
      loading: {
        true: 'cursor-wait relative',
        false: '',
      },
      fullWidth: {
        true: 'w-full',
        false: '',
      },
    },
    compoundVariants: [
      {
        intent: 'ghost',
        disabled: true,
        className: 'bg-transparent',
      },
      {
        intent: 'link',
        disabled: true,
        className: 'no-underline',
      },
    ],
  },
  slots: {
    start: {
      // Centred, not just sized. The slot is a fixed box per button size while
      // the content placed in it is whatever the caller passes — an `Icon` at
      // `size="sm"` is smaller than the box, and without centring it sits in
      // the top-left corner, which reads as a mis-aligned button.
      base: 'flex shrink-0 items-center justify-center',
      variants: {
        size: {
          sm: 'w-4 h-4',
          md: 'w-5 h-5',
          lg: 'w-6 h-6',
        },
      },
      modifiers: {},
    },
    end: {
      base: 'flex shrink-0 items-center justify-center',
      variants: {
        size: {
          sm: 'w-4 h-4',
          md: 'w-5 h-5',
          lg: 'w-6 h-6',
        },
      },
      modifiers: {},
    },
    loadingIndicator: {
      base: 'absolute',
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
    intent: 'primary',
    size: 'md',
  },
};
