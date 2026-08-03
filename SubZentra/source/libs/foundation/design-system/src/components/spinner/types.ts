/**
 * Spinner component type definitions
 * @module components/spinner/types
 */

import type {
  ComponentThemeConfigStructure,
  OIComponentOwnProps,
  OIComponentProps,
  OIComponentRef,
  OIDefaultProps,
} from '../../types';

/**
 * Spinner variant definitions
 */
export const SpinnerVariants = {
  size: ['xs', 'sm', 'md', 'lg', 'xl'] as const,
} as const;

/**
 * Spinner modifier definitions
 */
export const SpinnerModifiers = [] as const;

/**
 * Spinner slot definitions
 */
export const SpinnerSlots = [] as const;

/**
 * Spinner's own props
 */
export interface SpinnerOwnProps
  extends OIComponentOwnProps<
    typeof SpinnerVariants,
    typeof SpinnerModifiers,
    typeof SpinnerSlots
  > {
  /** Accessible label for screen readers */
  'aria-label'?: string;
}

/**
 * Spinner component props
 */
export type SpinnerProps<T extends React.ElementType = 'span'> = OIComponentProps<
  T,
  SpinnerOwnProps & OIDefaultProps
>;

/**
 * Spinner component type
 */
export type SpinnerComponent = <T extends React.ElementType = 'span'>(
  props: SpinnerProps<T> & { ref?: OIComponentRef<T> },
) => React.ReactNode;

/**
 * Default theme configuration for Spinner
 */
export const spinnerDefaultTheme: ComponentThemeConfigStructure = {
  root: {
    base: 'inline-block animate-spin rounded-full border-2 border-current border-t-transparent',
    variants: {
      size: {
        xs: 'h-3 w-3 border',
        sm: 'h-4 w-4',
        md: 'h-5 w-5',
        lg: 'h-6 w-6',
        xl: 'h-8 w-8 border-[3px]',
      },
    },
    modifiers: {},
  },
  defaultVariants: {
    size: 'md',
  },
};
