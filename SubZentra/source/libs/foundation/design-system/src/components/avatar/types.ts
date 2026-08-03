/**
 * Avatar component type definitions
 * @module components/avatar/types
 */

import type {
  ComponentThemeConfigStructure,
  OIComponentOwnProps,
  OIComponentSlotProps,
  PolymorphicProps,
  PolymorphicRef,
} from '../../types';

/**
 * Avatar variant definitions
 */
export const AvatarVariants = {
  size: ['xs', 'sm', 'md', 'lg', 'xl', '2xl'] as const,
  shape: ['circle', 'square'] as const,
  status: ['online', 'offline', 'away', 'busy', 'none'] as const,
} as const;

/**
 * Avatar modifier definitions
 */
export const AvatarModifiers = ['skeleton', 'hasContext'] as const;

/**
 * Avatar slot definitions
 */
export const AvatarSlots = ['context', 'fallback'] as const;

/**
 * Avatar's own props
 */
export interface AvatarOwnProps
  extends OIComponentOwnProps<typeof AvatarVariants, typeof AvatarModifiers, typeof AvatarSlots> {
  /** Size of the avatar */
  size?: (typeof AvatarVariants.size)[number];
  /** Shape of the avatar */
  shape?: (typeof AvatarVariants.shape)[number];
  /** Online status indicator */
  status?: (typeof AvatarVariants.status)[number];
  /** Image source URL */
  src?: string;
  /** Alt text for the avatar image */
  alt?: string;
  /** User's name for initials fallback */
  name?: string;
  /** Show skeleton loading state */
  skeleton?: boolean;
  /** Context icon/element slot (appears in corner) */
  context?: OIComponentSlotProps;
  /**
   * Whether the avatar is styled as having a context slot.
   *
   * Derived from `context` when not given. It is settable because it is a
   * declared modifier, and a declared modifier a caller cannot set is one the
   * theme can style but nobody can trigger.
   */
  hasContext?: boolean;
  /** Fallback content when image fails or no src provided */
  fallback?: OIComponentSlotProps;
  /** Callback when image fails to load */
  onError?: () => void;
}

/**
 * Avatar component props
 */
export type AvatarProps<T extends React.ElementType = 'div'> = PolymorphicProps<T, AvatarOwnProps>;

/**
 * Avatar component ref type
 */
export type AvatarRef<T extends React.ElementType = 'div'> = PolymorphicRef<T>;

/**
 * Avatar component type
 */
export interface AvatarComponent {
  <T extends React.ElementType = 'div'>(
    props: AvatarProps<T> & { ref?: AvatarRef<T> },
  ): React.ReactNode;
  displayName?: string;
}

/**
 * Default theme configuration for Avatar
 */
export const avatarDefaultTheme: ComponentThemeConfigStructure = {
  root: {
    base: 'relative inline-flex shrink-0 items-center justify-center overflow-hidden bg-muted',
    variants: {
      size: {
        xs: 'h-6 w-6 text-[10px]',
        sm: 'h-8 w-8 text-xs',
        md: 'h-10 w-10 text-sm',
        lg: 'h-12 w-12 text-base',
        xl: 'h-14 w-14 text-lg',
        '2xl': 'h-16 w-16 text-xl',
      },
      shape: {
        circle: 'rounded-full',
        square: 'rounded-md',
      },
      status: {
        online: '',
        offline: '',
        away: '',
        busy: '',
        none: '',
      },
    },
    modifiers: {
      skeleton: {
        true: 'animate-pulse',
        false: '',
      },
      hasContext: {
        true: '',
        false: '',
      },
    },
  },
  slots: {
    image: {
      base: 'h-full w-full object-cover',
      variants: {
        size: {
          xs: '',
          sm: '',
          md: '',
          lg: '',
          xl: '',
          '2xl': '',
        },
        shape: {
          circle: '',
          square: '',
        },
      },
      modifiers: {},
    },
    fallback: {
      base: 'flex h-full w-full items-center justify-center font-medium text-muted-foreground uppercase',
      variants: {
        size: {
          xs: '',
          sm: '',
          md: '',
          lg: '',
          xl: '',
          '2xl': '',
        },
      },
      modifiers: {},
    },
    statusIndicator: {
      base: 'absolute bottom-0 right-0 block rounded-full ring-2 ring-background',
      variants: {
        size: {
          xs: 'h-1.5 w-1.5',
          sm: 'h-2 w-2',
          md: 'h-2.5 w-2.5',
          lg: 'h-3 w-3',
          xl: 'h-3.5 w-3.5',
          '2xl': 'h-4 w-4',
        },
        status: {
          online: 'bg-green-500',
          offline: 'bg-gray-400',
          away: 'bg-yellow-500',
          busy: 'bg-red-500',
          none: 'hidden',
        },
      },
      modifiers: {},
    },
    context: {
      base: 'absolute -bottom-0.5 -right-0.5 flex items-center justify-center rounded-full bg-background ring-2 ring-background',
      variants: {
        size: {
          xs: 'h-3 w-3',
          sm: 'h-4 w-4',
          md: 'h-5 w-5',
          lg: 'h-6 w-6',
          xl: 'h-7 w-7',
          '2xl': 'h-8 w-8',
        },
      },
      modifiers: {},
    },
  },
  defaultVariants: {
    size: 'md',
    shape: 'circle',
    status: 'none',
  },
};
