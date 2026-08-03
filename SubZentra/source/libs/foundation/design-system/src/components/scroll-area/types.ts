/**
 * ScrollArea component type definitions
 * @module components/scroll-area/types
 */

import type {
  ComponentThemeConfigStructure,
  OIComponentOwnProps,
  PolymorphicProps,
  PolymorphicRef,
} from '../../types';

/**
 * ScrollArea variant definitions
 */
export const ScrollAreaVariants = {
  orientation: ['vertical', 'horizontal', 'both'] as const,
  type: ['hover', 'scroll', 'always'] as const,
} as const;

/**
 * ScrollArea modifier definitions
 */
export const ScrollAreaModifiers = [] as const;

/**
 * ScrollArea slot definitions
 */
export const ScrollAreaSlots = [] as const;

/**
 * ScrollArea's own props
 */
export interface ScrollAreaOwnProps
  extends OIComponentOwnProps<
    typeof ScrollAreaVariants,
    typeof ScrollAreaModifiers,
    typeof ScrollAreaSlots
  > {
  /** Scrollbar orientation */
  orientation?: (typeof ScrollAreaVariants.orientation)[number];
  /** When to show scrollbars */
  type?: (typeof ScrollAreaVariants.type)[number];
  /** Height of the scroll area */
  height?: string | number;
  /** Maximum height of the scroll area */
  maxHeight?: string | number;
  /** Reference to the viewport element */
  viewportRef?: React.RefObject<HTMLDivElement>;
  /** Scroll area content */
  children?: React.ReactNode;
}

/**
 * ScrollArea component props
 */
export type ScrollAreaProps<T extends React.ElementType = 'div'> = PolymorphicProps<
  T,
  ScrollAreaOwnProps
>;

/**
 * ScrollArea component ref type
 */
export type ScrollAreaRef<T extends React.ElementType = 'div'> = PolymorphicRef<T>;

/**
 * ScrollArea component type
 */
export interface ScrollAreaComponent {
  <T extends React.ElementType = 'div'>(
    props: ScrollAreaProps<T> & { ref?: ScrollAreaRef<T> },
  ): React.ReactNode;
  displayName?: string;
}

/**
 * Default theme configuration for ScrollArea
 */
export const scrollAreaDefaultTheme: ComponentThemeConfigStructure = {
  root: {
    base: 'relative overflow-hidden',
    variants: {
      orientation: {
        vertical: '',
        horizontal: '',
        both: '',
      },
      type: {
        hover: '',
        scroll: '',
        always: '',
      },
    },
    modifiers: {},
  },
  slots: {
    viewport: {
      base: 'h-full w-full rounded-[inherit]',
      variants: {
        orientation: {
          vertical: 'overflow-y-auto overflow-x-hidden',
          horizontal: 'overflow-x-auto overflow-y-hidden',
          both: 'overflow-auto',
        },
      },
      modifiers: {},
    },
    scrollbar: {
      base: 'flex touch-none select-none transition-colors',
      variants: {
        orientation: {
          vertical: 'h-full w-2.5 border-l border-l-transparent p-px',
          horizontal: 'h-2.5 flex-col border-t border-t-transparent p-px',
          both: '',
        },
      },
      modifiers: {},
    },
    scrollbarVertical: {
      base: 'absolute right-0 top-0 h-full w-2.5 border-l border-l-transparent p-px',
      variants: {
        type: {
          hover: 'opacity-0 transition-opacity group-hover:opacity-100',
          scroll: '',
          always: '',
        },
      },
      modifiers: {},
    },
    scrollbarHorizontal: {
      base: 'absolute bottom-0 left-0 h-2.5 w-full flex-col border-t border-t-transparent p-px',
      variants: {
        type: {
          hover: 'opacity-0 transition-opacity group-hover:opacity-100',
          scroll: '',
          always: '',
        },
      },
      modifiers: {},
    },
    thumb: {
      base: 'relative flex-1 rounded-full bg-border',
      variants: {},
      modifiers: {},
    },
    corner: {
      base: 'bg-muted',
      variants: {},
      modifiers: {},
    },
  },
  defaultVariants: {
    orientation: 'vertical',
    type: 'hover',
  },
};
