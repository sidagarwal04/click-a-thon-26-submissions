/**
 * Banner component type definitions
 * @module components/banner/types
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
 * Banner variant definitions
 */
export const BannerVariants = {
  variant: ['info', 'success', 'warning', 'error'] as const,
  type: ['inline', 'section'] as const,
} as const;

/**
 * Banner modifier definitions
 */
export const BannerModifiers = ['spotlight', 'dismissible'] as const;

/**
 * Banner slot definitions
 */
export const BannerSlots = ['icon'] as const;

/**
 * Banner's own props
 */
export interface BannerOwnProps
  extends OIComponentOwnProps<typeof BannerVariants, typeof BannerModifiers, typeof BannerSlots> {
  /** Feedback variant */
  variant?: (typeof BannerVariants.variant)[number];
  /** Banner type */
  type?: (typeof BannerVariants.type)[number];
  /** Highlight the banner with stronger styling */
  spotlight?: boolean;
  /** Whether the banner can be dismissed */
  dismissible?: boolean;
  /** Icon slot (typically feedback icon) */
  icon?: OIComponentSlotProps;
  /** Callback when banner is dismissed */
  onDismiss?: () => void;
  /** Children (typically Banner.Title, Banner.Description, Banner.Actions) */
  children?: React.ReactNode;
}

/**
 * Banner component props
 */
export type BannerProps<T extends React.ElementType = 'div'> = PolymorphicProps<T, BannerOwnProps>;

/**
 * Banner component ref type
 */
export type BannerRef<T extends React.ElementType = 'div'> = PolymorphicRef<T>;

// Sub-component props
export interface BannerTitleProps extends OIDefaultProps {
  children?: React.ReactNode;
  className?: string;
}

export interface BannerDescriptionProps extends OIDefaultProps {
  children?: React.ReactNode;
  className?: string;
}

export interface BannerBodyProps extends OIDefaultProps {
  children?: React.ReactNode;
  className?: string;
}

export interface BannerActionsProps extends OIDefaultProps {
  children?: React.ReactNode;
  className?: string;
}

export interface BannerCloseProps extends OIDefaultProps {
  className?: string;
}

/**
 * Banner context value for ARIA and dismiss handling
 */
export interface BannerContextValue {
  titleId: string;
  descriptionId: string;
  variant: (typeof BannerVariants.variant)[number];
  onDismiss?: () => void;
}

/**
 * Banner component type with sub-components
 */
export interface BannerComponent {
  <T extends React.ElementType = 'div'>(
    props: BannerProps<T> & { ref?: BannerRef<T> },
  ): React.ReactNode;
  displayName?: string;
  Title: React.FC<BannerTitleProps>;
  Description: React.FC<BannerDescriptionProps>;
  Body: React.FC<BannerBodyProps>;
  Actions: React.FC<BannerActionsProps>;
  Close: React.FC<BannerCloseProps>;
}

/**
 * Default theme configuration for Banner
 */
export const bannerDefaultTheme: ComponentThemeConfigStructure = {
  root: {
    base: 'relative flex gap-3 rounded-lg border p-4',
    variants: {
      variant: {
        info: 'bg-blue-50 border-blue-200 dark:bg-blue-950/30 dark:border-blue-800',
        success: 'bg-green-50 border-green-200 dark:bg-green-950/30 dark:border-green-800',
        warning: 'bg-yellow-50 border-yellow-200 dark:bg-yellow-950/30 dark:border-yellow-800',
        error: 'bg-red-50 border-red-200 dark:bg-red-950/30 dark:border-red-800',
      },
      type: {
        inline: '',
        section: 'rounded-none border-x-0',
      },
    },
    modifiers: {
      spotlight: {
        true: 'border-l-4',
        false: '',
      },
      dismissible: {
        true: 'pr-10',
        false: '',
      },
    },
  },
  slots: {
    icon: {
      base: 'shrink-0 mt-0.5',
      variants: {
        variant: {
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
      base: 'font-semibold',
      variants: {
        variant: {
          info: 'text-blue-800 dark:text-blue-200',
          success: 'text-green-800 dark:text-green-200',
          warning: 'text-yellow-800 dark:text-yellow-200',
          error: 'text-red-800 dark:text-red-200',
        },
      },
      modifiers: {},
    },
    description: {
      base: 'text-sm mt-1',
      variants: {
        variant: {
          info: 'text-blue-700 dark:text-blue-300',
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
    close: {
      base: 'absolute right-2 top-2 rounded-md p-1 hover:bg-black/10 dark:hover:bg-white/10 focus:outline-none focus:ring-2 focus:ring-offset-1',
      variants: {
        variant: {
          info: 'text-blue-500 hover:text-blue-700',
          success: 'text-green-500 hover:text-green-700',
          warning: 'text-yellow-500 hover:text-yellow-700',
          error: 'text-red-500 hover:text-red-700',
        },
      },
      modifiers: {},
    },
  },
  defaultVariants: {
    variant: 'info',
    type: 'inline',
  },
};
