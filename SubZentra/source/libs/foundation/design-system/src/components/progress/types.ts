/**
 * Progress component type definitions
 * @module components/progress/types
 */

import type {
  ComponentThemeConfigStructure,
  OIComponentOwnProps,
  OIComponentRef,
  OIDefaultProps,
} from '../../types';

/**
 * Progress variant definitions
 */
export const ProgressVariants = {
  intent: ['primary', 'success', 'warning', 'danger'] as const,
  size: ['sm', 'md', 'lg'] as const,
} as const;

/**
 * Progress modifier definitions
 */
export const ProgressModifiers = ['indeterminate'] as const;

/**
 * Progress slot definitions
 */
export const ProgressSlots = ['indicator'] as const;

/**
 * Progress's own props
 */
export interface ProgressOwnProps
  extends OIComponentOwnProps<
    typeof ProgressVariants,
    typeof ProgressModifiers,
    typeof ProgressSlots
  > {
  /** Current progress value (0-100) */
  value?: number;
  /** Maximum value */
  max?: number;
  /** Accessible label */
  'aria-label'?: string;
  /** Label ID for aria-labelledby */
  'aria-labelledby'?: string;
}

/**
 * Progress component props
 */
export type ProgressProps = OIDefaultProps &
  ProgressOwnProps &
  Omit<React.HTMLAttributes<HTMLDivElement>, keyof ProgressOwnProps | 'className'>;

/**
 * Progress component type
 */
export type ProgressComponent = React.ForwardRefExoticComponent<
  ProgressProps & { ref?: OIComponentRef<'div'> }
>;

/**
 * Default theme configuration for Progress
 */
export const progressDefaultTheme: ComponentThemeConfigStructure = {
  root: {
    base: 'relative w-full overflow-hidden rounded-full bg-background-muted',
    variants: {
      intent: {
        primary: '',
        success: '',
        warning: '',
        danger: '',
      },
      size: {
        sm: 'h-1',
        md: 'h-2',
        lg: 'h-4',
      },
    },
    modifiers: {
      indeterminate: {
        true: '',
        false: '',
      },
    },
  },
  slots: {
    indicator: {
      base: 'h-full transition-all duration-300 ease-out',
      variants: {
        intent: {
          primary: 'bg-primary',
          success: 'bg-success',
          warning: 'bg-warning',
          danger: 'bg-danger',
        },
        size: {
          sm: '',
          md: '',
          lg: '',
        },
      },
      modifiers: {
        indeterminate: {
          true: 'animate-progress-indeterminate',
          false: '',
        },
      },
    },
  },
  defaultVariants: {
    intent: 'primary',
    size: 'md',
  },
};
