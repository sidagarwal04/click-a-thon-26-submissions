/**
 * SideNav component type definitions
 * @module components/side-nav/types
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
 * SideNav variant definitions
 */
export const SideNavVariants = {
  width: ['compact', 'default'] as const,
} as const;

/**
 * SideNav modifier definitions
 */
export const SideNavModifiers = [] as const;

/**
 * SideNav slot definitions
 */
export const SideNavSlots = ['brand', 'footer'] as const;

/**
 * SideNav's own props
 */
export interface SideNavOwnProps
  extends OIComponentOwnProps<
    typeof SideNavVariants,
    typeof SideNavModifiers,
    typeof SideNavSlots
  > {
  /** Rail width */
  width?: (typeof SideNavVariants.width)[number];
  /** Product mark or workspace switcher, pinned to the top of the rail */
  brand?: OIComponentSlotProps;
  /** Content pinned to the bottom of the rail */
  footer?: OIComponentSlotProps;
  /** Navigation items */
  children?: React.ReactNode;
}

/**
 * SideNav component props
 */
export type SideNavProps<T extends React.ElementType = 'nav'> = PolymorphicProps<
  T,
  SideNavOwnProps
>;

/**
 * SideNav component ref type
 */
export type SideNavRef<T extends React.ElementType = 'nav'> = PolymorphicRef<T>;

/**
 * SideNav.Item's own props
 */
export interface SideNavItemOwnProps extends OIDefaultProps {
  /** Leading icon */
  icon?: OIComponentSlotProps;
  /** Marks the destination the user is currently on */
  active?: boolean;
  /** Label */
  children?: React.ReactNode;
}

/**
 * SideNav.Item props
 *
 * Polymorphic so a router link can be supplied: `component={Link} to="/chat"`.
 */
export type SideNavItemProps<T extends React.ElementType = 'a'> = PolymorphicProps<
  T,
  SideNavItemOwnProps
>;

export interface SideNavItemComponent {
  <T extends React.ElementType = 'a'>(
    props: SideNavItemProps<T> & { ref?: PolymorphicRef<T> },
  ): React.ReactNode;
  displayName?: string;
}

/**
 * SideNav component type with sub-components
 */
export interface SideNavComponent {
  <T extends React.ElementType = 'nav'>(
    props: SideNavProps<T> & { ref?: SideNavRef<T> },
  ): React.ReactNode;
  displayName?: string;
  Item: SideNavItemComponent;
}

/**
 * Default theme configuration for SideNav
 */
export const sideNavDefaultTheme: ComponentThemeConfigStructure = {
  root: {
    // `group` so the collapsed state set on the rail can reach the items:
    // labels hide and rows centre from one attribute rather than every item
    // being told what width its parent is.
    base: 'group flex h-full shrink-0 flex-col gap-6 border-r border-border bg-card py-5 transition-[width] duration-200',
    variants: {
      width: {
        // Wide enough for a 44px tile plus even gutters, so the collapsed rail
        // is a column of squares rather than icons pushed against an edge.
        compact: 'w-[4.75rem] items-center px-4',
        default: 'w-60 px-3',
      },
    },
    modifiers: {},
  },
  slots: {
    brand: {
      base: 'px-2 group-data-[collapsed=true]:flex group-data-[collapsed=true]:justify-center group-data-[collapsed=true]:px-0',
      variants: {},
      modifiers: {},
    },
    list: {
      base: 'flex flex-1 flex-col gap-1 group-data-[collapsed=true]:w-full group-data-[collapsed=true]:items-center group-data-[collapsed=true]:gap-2',
      variants: {},
      modifiers: {},
    },
    footer: {
      base: 'mt-auto flex flex-col gap-2 group-data-[collapsed=true]:w-full group-data-[collapsed=true]:items-center group-data-[collapsed=true]:gap-3',
      variants: {},
      modifiers: {},
    },
    item: {
      // Collapsed, an item is a fixed square tile: equal sides and no padding
      // of its own, so the row of icons reads as a column of even blocks
      // instead of text rows that lost their text.
      base: 'flex items-center gap-3 rounded-md px-3 py-2 text-sm no-underline transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-border-focus group-data-[collapsed=true]:h-11 group-data-[collapsed=true]:w-11 group-data-[collapsed=true]:justify-center group-data-[collapsed=true]:gap-0 group-data-[collapsed=true]:p-0',
      variants: {},
      modifiers: {
        active: {
          true: 'bg-accent text-accent-foreground font-medium',
          false: 'text-foreground-muted hover:bg-secondary hover:text-foreground',
        },
      },
    },
    itemIcon: {
      base: 'flex shrink-0 items-center justify-center [&>svg]:h-4 [&>svg]:w-4 group-data-[collapsed=true]:[&>svg]:h-5 group-data-[collapsed=true]:[&>svg]:w-5',
      variants: {},
      modifiers: {},
    },
    itemLabel: {
      // `sr-only` rather than `hidden` when collapsed: `display: none` would
      // take the label out of the accessibility tree and leave the link with
      // no accessible name at all.
      base: 'truncate group-data-[collapsed=true]:sr-only',
      variants: {},
      modifiers: {},
    },
  },
  defaultVariants: {
    width: 'default',
  },
};
