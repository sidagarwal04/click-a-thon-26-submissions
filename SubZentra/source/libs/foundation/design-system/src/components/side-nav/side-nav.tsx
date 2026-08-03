/**
 * SideNav component
 * @module components/side-nav
 */
import React from 'react';

import { Slot } from '../../primitives/slot';
import { useTheme } from '../../theme';
import { SideNavItem } from './side-nav-item';
import { SideNavContext } from './side-nav.context';
import type { SideNavComponent, SideNavProps } from './types';
import { sideNavDefaultTheme } from './types';

/**
 * SideNav component
 *
 * The primary navigation rail: a brand lockup, the destinations of the
 * product, and pinned footer content.
 *
 * Renders a `nav` element, so it needs an accessible name when a page has
 * more than one navigation landmark.
 *
 * @example
 * <SideNav aria-label="Primary" brand={<ProductMark />} footer={<Button>New</Button>}>
 *   <SideNav.Item component={Link} to="/" icon={<GridIcon />} active>
 *     Dashboard
 *   </SideNav.Item>
 * </SideNav>
 */
const SideNavRoot = React.forwardRef(function SideNav<T extends React.ElementType = 'nav'>(
  { component, className, children, ozid, width = 'default', brand, footer, ...rest }: SideNavProps<T>,
  ref: React.ForwardedRef<Element>,
) {
  const theme = useTheme('sideNav', sideNavDefaultTheme);
  const Element = component ?? 'nav';
  const context = React.useMemo(() => ({ width }), [width]);

  return (
    <Element
      ref={ref}
      className={theme.root({ className, width })}
      data-ozid={ozid}
      // Read by the items through the root's `group`, so a collapsed rail
      // hides its labels without every item being handed the width.
      data-collapsed={width === 'compact' ? 'true' : undefined}
      {...rest}
    >
      <SideNavContext.Provider value={context}>
        {brand && (
          <Slot
            baseOzid={ozid}
            className={theme.brand?.({}) ?? ''}
            slotName="brand"
            slot={brand}
            component="div"
          />
        )}

        <div className={theme.list?.({}) ?? ''}>{children}</div>

        {footer && (
          <Slot
            baseOzid={ozid}
            className={theme.footer?.({}) ?? ''}
            slotName="footer"
            slot={footer}
            component="div"
          />
        )}
      </SideNavContext.Provider>
    </Element>
  );
}) as unknown as SideNavComponent;

SideNavRoot.displayName = 'SideNav';
SideNavRoot.Item = SideNavItem;

export const SideNav = SideNavRoot;
