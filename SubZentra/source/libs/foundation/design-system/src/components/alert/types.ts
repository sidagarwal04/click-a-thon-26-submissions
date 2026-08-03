/**
 * Alert component type definitions
 * @module components/alert/types
 */

import type {
  ComponentThemeConfigStructure,
  OIComponentSlotProps,
  OIDefaultProps,
  PolymorphicProps,
  PolymorphicRef,
} from '../../types';

/**
 * Alert variant definitions
 */
export const AlertVariants = {
  intent: ['info', 'success', 'warning', 'error'] as const,
} as const;

/**
 * Alert modifier definitions
 */
export const AlertModifiers = ['dismissible'] as const;

/**
 * Alert slot definitions
 */
export const AlertSlots = ['start', 'end'] as const;

/**
 * Alert's own props
 */
export interface AlertOwnProps extends OIDefaultProps {
  /** Alert intent/style variant */
  intent?: (typeof AlertVariants.intent)[number];
  /** Dismissible state */
  dismissible?: boolean;
  /** Start slot (icon or content before text) */
  start?: OIComponentSlotProps;
  /** End slot (dismiss button or custom content) */
  end?: OIComponentSlotProps;
  /** Alert title */
  title?: React.ReactNode;
  /** Alert content */
  children?: React.ReactNode;
  /** Called when dismiss button is clicked */
  onDismiss?: () => void;
}

/**
 * Alert component props
 */
export type AlertProps<T extends React.ElementType = 'div'> = PolymorphicProps<T, AlertOwnProps>;

/**
 * Alert component ref type
 */
export type AlertRef<T extends React.ElementType = 'div'> = PolymorphicRef<T>;

/**
 * Alert component type
 */
export interface AlertComponent {
  <T extends React.ElementType = 'div'>(
    props: AlertProps<T> & { ref?: AlertRef<T> },
  ): React.ReactNode;
  displayName?: string;
}

/**
 * Default theme configuration for Alert
 */
export const alertDefaultTheme: ComponentThemeConfigStructure = {
  root: {
    base: 'relative flex gap-3 rounded-lg border p-4',
    variants: {
      intent: {
        info: 'bg-info/10 border-info/20 text-info-foreground [&_svg]:text-info',
        success: 'bg-success/10 border-success/20 text-success-foreground [&_svg]:text-success',
        warning: 'bg-warning/10 border-warning/20 text-warning-foreground [&_svg]:text-warning',
        error: 'bg-danger/10 border-danger/20 text-danger-foreground [&_svg]:text-danger',
      },
    },
    modifiers: {
      dismissible: {
        true: 'pr-10',
        false: '',
      },
    },
  },
  slots: {
    start: {
      base: 'shrink-0 mt-0.5',
      variants: {
        intent: {
          info: 'text-info',
          success: 'text-success',
          warning: 'text-warning',
          error: 'text-danger',
        },
      },
      modifiers: {},
    },
    end: {
      base: 'absolute right-2 top-2 shrink-0 rounded-sm opacity-70 hover:opacity-100 transition-opacity cursor-pointer p-1',
      variants: {
        intent: {
          info: 'hover:bg-info/20',
          success: 'hover:bg-success/20',
          warning: 'hover:bg-warning/20',
          error: 'hover:bg-danger/20',
        },
      },
      modifiers: {},
    },
  },
  defaultVariants: {
    intent: 'info',
  },
};
