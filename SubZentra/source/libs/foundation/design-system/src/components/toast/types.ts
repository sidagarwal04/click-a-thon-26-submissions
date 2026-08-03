/**
 * Toast component type definitions
 * @module components/toast/types
 */

import type {
  ComponentThemeConfigStructure,
  OIComponentOwnProps,
  OIComponentSlotProps,
  OIDefaultProps,
  PolymorphicProps,
  PolymorphicRef,
} from '../../types';

/**
 * Toast variant definitions
 */
export const ToastVariants = {
  feedback: ['info', 'success', 'warning', 'error'] as const,
} as const;

/**
 * Toast modifier definitions
 */
export const ToastModifiers = ['closable'] as const;

/**
 * Toast slot definitions
 */
export const ToastSlots = ['start', 'end', 'close'] as const;

/**
 * Toast's own props
 */
export interface ToastOwnProps
  extends OIComponentOwnProps<typeof ToastVariants, typeof ToastModifiers, typeof ToastSlots> {
  /** Feedback variant */
  feedback?: (typeof ToastVariants.feedback)[number];
  /** Whether the toast can be closed */
  closable?: boolean;
  /** Content for the start slot (typically an icon) */
  start?: OIComponentSlotProps;
  /** Content for the end slot */
  end?: OIComponentSlotProps;
  /** Custom close button content */
  close?: OIComponentSlotProps;
  /** Callback when close button is clicked */
  onClose?: () => void;
  /** Children (typically Toast.Title, Toast.Description, Toast.Actions) */
  children?: React.ReactNode;
}

/**
 * Toast component props
 */
export type ToastProps<T extends React.ElementType = 'div'> = PolymorphicProps<T, ToastOwnProps>;

/**
 * Toast component ref type
 */
export type ToastRef<T extends React.ElementType = 'div'> = PolymorphicRef<T>;

// Sub-component props
export interface ToastTitleProps extends OIDefaultProps {
  children?: React.ReactNode;
  className?: string;
}

export interface ToastDescriptionProps extends OIDefaultProps {
  children?: React.ReactNode;
  className?: string;
}

export interface ToastBodyProps extends OIDefaultProps {
  children?: React.ReactNode;
  className?: string;
}

export interface ToastActionsProps extends OIDefaultProps {
  children?: React.ReactNode;
  className?: string;
}

/**
 * Toast component type with sub-components
 */
export interface ToastComponent {
  <T extends React.ElementType = 'div'>(
    props: ToastProps<T> & { ref?: ToastRef<T> },
  ): React.ReactNode;
  displayName?: string;
  Title: React.FC<ToastTitleProps>;
  Description: React.FC<ToastDescriptionProps>;
  Body: React.FC<ToastBodyProps>;
  Actions: React.FC<ToastActionsProps>;
}

/**
 * Default theme configuration for Toast
 */
export const toastDefaultTheme: ComponentThemeConfigStructure = {
  root: {
    base: 'relative flex w-full items-start gap-3 rounded-lg border p-4 shadow-lg',
    variants: {
      feedback: {
        info: 'bg-background border-border',
        success: 'bg-green-50 border-green-200 dark:bg-green-950/30 dark:border-green-800',
        warning: 'bg-yellow-50 border-yellow-200 dark:bg-yellow-950/30 dark:border-yellow-800',
        error: 'bg-red-50 border-red-200 dark:bg-red-950/30 dark:border-red-800',
      },
    },
    modifiers: {
      closable: {
        true: 'pr-10',
        false: '',
      },
    },
  },
  slots: {
    start: {
      base: 'shrink-0 mt-0.5',
      variants: {
        feedback: {
          info: 'text-blue-500',
          success: 'text-green-500',
          warning: 'text-yellow-500',
          error: 'text-red-500',
        },
      },
      modifiers: {},
    },
    content: {
      base: 'flex-1 min-w-0',
      variants: {},
      modifiers: {},
    },
    title: {
      base: 'font-semibold text-foreground',
      variants: {
        feedback: {
          info: '',
          success: 'text-green-800 dark:text-green-200',
          warning: 'text-yellow-800 dark:text-yellow-200',
          error: 'text-red-800 dark:text-red-200',
        },
      },
      modifiers: {},
    },
    description: {
      base: 'text-sm text-muted-foreground mt-1',
      variants: {
        feedback: {
          info: '',
          success: 'text-green-700 dark:text-green-300',
          warning: 'text-yellow-700 dark:text-yellow-300',
          error: 'text-red-700 dark:text-red-300',
        },
      },
      modifiers: {},
    },
    body: {
      base: 'mt-2',
      variants: {},
      modifiers: {},
    },
    actions: {
      base: 'flex items-center gap-2 mt-3',
      variants: {},
      modifiers: {},
    },
    end: {
      base: 'shrink-0',
      variants: {},
      modifiers: {},
    },
    close: {
      base: 'absolute right-2 top-2 rounded-md p-1 text-muted-foreground hover:text-foreground hover:bg-muted/50 focus:outline-none focus:ring-2 focus:ring-offset-1',
      variants: {
        feedback: {
          info: '',
          success: 'hover:bg-green-100 dark:hover:bg-green-900/50',
          warning: 'hover:bg-yellow-100 dark:hover:bg-yellow-900/50',
          error: 'hover:bg-red-100 dark:hover:bg-red-900/50',
        },
      },
      modifiers: {},
    },
  },
  defaultVariants: {
    feedback: 'info',
  },
};
