/**
 * EmptyState component type definitions
 * @module components/empty-state/types
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
 * EmptyState variant definitions
 */
export const EmptyStateVariants = {
  size: ['sm', 'md', 'lg'] as const,
} as const;

/**
 * EmptyState modifier definitions
 */
export const EmptyStateModifiers = ['compact'] as const;

/**
 * EmptyState slot definitions
 */
export const EmptyStateSlots = ['icon'] as const;

/**
 * EmptyState's own props
 */
export interface EmptyStateOwnProps
  extends OIComponentOwnProps<
    typeof EmptyStateVariants,
    typeof EmptyStateModifiers,
    typeof EmptyStateSlots
  > {
  /** Size variant */
  size?: (typeof EmptyStateVariants.size)[number];
  /** Compact mode with less padding */
  compact?: boolean;
  /** Icon or illustration slot */
  icon?: OIComponentSlotProps;
  /** Children (typically EmptyState.Title, EmptyState.Description, EmptyState.Actions) */
  children?: React.ReactNode;
}

/**
 * EmptyState component props
 */
export type EmptyStateProps<T extends React.ElementType = 'div'> = PolymorphicProps<
  T,
  EmptyStateOwnProps
>;

/**
 * EmptyState component ref type
 */
export type EmptyStateRef<T extends React.ElementType = 'div'> = PolymorphicRef<T>;

// Sub-component props
export interface EmptyStateTitleProps extends OIDefaultProps {
  children?: React.ReactNode;
  className?: string;
}

export interface EmptyStateDescriptionProps extends OIDefaultProps {
  children?: React.ReactNode;
  className?: string;
}

export interface EmptyStateActionsProps extends OIDefaultProps {
  children?: React.ReactNode;
  className?: string;
}

/**
 * EmptyState component type with sub-components
 */
export interface EmptyStateComponent {
  <T extends React.ElementType = 'div'>(
    props: EmptyStateProps<T> & { ref?: EmptyStateRef<T> },
  ): React.ReactNode;
  displayName?: string;
  Title: React.FC<EmptyStateTitleProps>;
  Description: React.FC<EmptyStateDescriptionProps>;
  Actions: React.FC<EmptyStateActionsProps>;
}

/**
 * Default theme configuration for EmptyState
 */
export const emptyStateDefaultTheme: ComponentThemeConfigStructure = {
  root: {
    base: 'flex flex-col items-center justify-center text-center',
    variants: {
      size: {
        sm: 'gap-2 p-4',
        md: 'gap-3 p-6',
        lg: 'gap-4 p-8',
      },
    },
    modifiers: {
      compact: {
        true: 'p-2',
        false: '',
      },
    },
  },
  slots: {
    icon: {
      base: 'text-muted-foreground',
      variants: {
        size: {
          sm: '[&>svg]:h-8 [&>svg]:w-8',
          md: '[&>svg]:h-12 [&>svg]:w-12',
          lg: '[&>svg]:h-16 [&>svg]:w-16',
        },
      },
      modifiers: {},
    },
    title: {
      base: 'font-semibold text-foreground',
      variants: {
        size: {
          sm: 'text-sm',
          md: 'text-base',
          lg: 'text-lg',
        },
      },
      modifiers: {},
    },
    description: {
      base: 'text-muted-foreground max-w-sm',
      variants: {
        size: {
          sm: 'text-xs',
          md: 'text-sm',
          lg: 'text-sm',
        },
      },
      modifiers: {},
    },
    actions: {
      base: 'flex flex-wrap items-center justify-center gap-2',
      variants: {
        size: {
          sm: 'mt-2',
          md: 'mt-3',
          lg: 'mt-4',
        },
      },
      modifiers: {},
    },
  },
  defaultVariants: {
    size: 'md',
  },
};
