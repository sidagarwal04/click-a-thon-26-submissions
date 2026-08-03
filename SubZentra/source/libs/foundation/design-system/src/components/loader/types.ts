/**
 * Loader component type definitions
 * @module components/loader/types
 */

import type {
  ComponentThemeConfigStructure,
  OIComponentSlotProps,
  OIDefaultProps,
  PolymorphicProps,
  PolymorphicRef,
} from '../../types';

/**
 * Loader variant definitions
 */
export const LoaderVariants = {
  size: ['sm', 'md', 'lg', 'xl'] as const,
  variant: ['spinner', 'dots', 'skeleton'] as const,
} as const;

/**
 * Loader modifier definitions
 */
export const LoaderModifiers = ['fullScreen', 'overlay', 'inline'] as const;

/**
 * Loader slot definitions
 */
export const LoaderSlots = ['indicator', 'label'] as const;

/**
 * Loader's own props
 */
export interface LoaderOwnProps extends OIDefaultProps {
  /** Loader size */
  size?: (typeof LoaderVariants.size)[number];
  /** Loader visual variant */
  variant?: (typeof LoaderVariants.variant)[number];
  /** Display as full screen overlay */
  fullScreen?: boolean;
  /** Display with semi-transparent overlay */
  overlay?: boolean;
  /** Display inline with content */
  inline?: boolean;
  /** Loading state - when false, children are rendered */
  loading?: boolean;
  /** Loading label text - can be a ReactNode or slot configuration */
  label?: OIComponentSlotProps;
  /** Custom loading indicator */
  indicator?: OIComponentSlotProps;
  /** Accessible label for screen readers */
  'aria-label'?: string;
  /** Children to render when not loading */
  children?: React.ReactNode;
}

/**
 * Loader component props
 */
export type LoaderProps<T extends React.ElementType = 'div'> = PolymorphicProps<T, LoaderOwnProps>;

/**
 * Loader component ref type
 */
export type LoaderRef<T extends React.ElementType = 'div'> = PolymorphicRef<T>;

/**
 * Loader component type
 */
export interface LoaderComponent {
  <T extends React.ElementType = 'div'>(
    props: LoaderProps<T> & { ref?: LoaderRef<T> },
  ): React.ReactNode;
  displayName?: string;
}

/**
 * Default theme configuration for Loader
 */
export const loaderDefaultTheme: ComponentThemeConfigStructure = {
  root: {
    base: 'flex flex-col items-center justify-center gap-3',
    variants: {
      size: {
        sm: 'gap-2',
        md: 'gap-3',
        lg: 'gap-4',
        xl: 'gap-5',
      },
      variant: {
        spinner: '',
        dots: '',
        skeleton: '',
      },
    },
    modifiers: {
      fullScreen: {
        true: 'fixed inset-0 z-50 bg-background',
        false: '',
      },
      overlay: {
        true: 'absolute inset-0 bg-background/80 backdrop-blur-sm',
        false: '',
      },
      inline: {
        true: 'flex-row',
        false: '',
      },
    },
  },
  slots: {
    indicator: {
      base: '',
      variants: {
        size: {
          sm: '',
          md: '',
          lg: '',
          xl: '',
        },
      },
      modifiers: {},
    },
    dot: {
      base: 'rounded-full bg-current animate-bounce',
      variants: {
        size: {
          sm: 'h-1.5 w-1.5',
          md: 'h-2 w-2',
          lg: 'h-2.5 w-2.5',
          xl: 'h-3 w-3',
        },
      },
      modifiers: {},
    },
    label: {
      base: 'text-muted-foreground',
      variants: {
        size: {
          sm: 'text-xs',
          md: 'text-sm',
          lg: 'text-base',
          xl: 'text-lg',
        },
      },
      modifiers: {},
    },
    wrapper: {
      base: 'relative',
      variants: {},
      modifiers: {
        overlay: {
          true: '',
          false: '',
        },
      },
    },
  },
  defaultVariants: {
    size: 'md',
    variant: 'spinner',
  },
};
