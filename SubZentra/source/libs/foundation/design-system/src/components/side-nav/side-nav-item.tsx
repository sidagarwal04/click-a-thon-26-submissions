/**
 * SideNav.Item sub-component
 * @module components/side-nav
 */
import React from 'react';

import { Slot } from '../../primitives/slot';
import { useTheme } from '../../theme';
import { Tooltip } from '../tooltip';
import { useSideNavContext } from './side-nav.context';
import type { SideNavItemComponent, SideNavItemProps } from './types';
import { sideNavDefaultTheme } from './types';

/**
 * SideNav.Item component
 *
 * One destination in the navigation rail.
 *
 * `aria-current="page"` rather than a styled state alone: the active item has
 * to be announced, not only coloured.
 *
 * On a collapsed rail the label is only visually hidden — so the link keeps its
 * accessible name — and a tooltip carries it for sighted users, who would
 * otherwise be reading an unlabelled icon.
 */
export const SideNavItem = React.forwardRef(function SideNavItem<
  T extends React.ElementType = 'a',
>(
  { component, className, children, ozid, icon, active, ...rest }: SideNavItemProps<T>,
  ref: React.ForwardedRef<Element>,
) {
  const theme = useTheme('sideNav', sideNavDefaultTheme);
  const { width } = useSideNavContext();
  const Element = component ?? 'a';

  const item = (
    <Element
      ref={ref}
      className={theme.item?.({ className, active: Boolean(active) }) ?? className}
      data-ozid={ozid}
      data-slot="item"
      aria-current={active ? 'page' : undefined}
      {...rest}
    >
      {icon && (
        <Slot
          baseOzid={ozid}
          className={theme.itemIcon?.({}) ?? ''}
          slotName="itemIcon"
          slot={icon}
          component="span"
          aria-hidden="true"
        />
      )}
      <span className={theme.itemLabel?.({}) ?? ''}>{children}</span>
    </Element>
  );

  if (width !== 'compact') return item;

  return (
    <Tooltip content={children} side="right" sideOffset={10}>
      {item}
    </Tooltip>
  );
}) as unknown as SideNavItemComponent;

SideNavItem.displayName = 'SideNav.Item';
