/**
 * Drawer component
 * @module components/drawer
 */
import { useId, useMemo } from 'react';

import { Dialog } from '@base-ui/react/dialog';

import { DrawerBody } from './drawer-body';
import { DrawerClose } from './drawer-close';
import { DrawerContent } from './drawer-content';
import { DrawerDescription } from './drawer-description';
import { DrawerFooter } from './drawer-footer';
import { DrawerHeader } from './drawer-header';
import { DrawerTitle } from './drawer-title';
import { DrawerTrigger } from './drawer-trigger';
import { DrawerContext } from './drawer.context';
import type { DrawerComponent, DrawerContextValue } from './types';

/**
 * Drawer component
 *
 * A sliding panel that appears from the edge of the screen.
 * Built on Base UI Dialog primitives.
 *
 * @example
 * <Drawer direction="right" size="1/3">
 *   <Drawer.Trigger asChild>
 *     <Button>Open Drawer</Button>
 *   </Drawer.Trigger>
 *   <Drawer.Content>
 *     <Drawer.Header>
 *       <Drawer.Title>Drawer Title</Drawer.Title>
 *       <Drawer.Description>Drawer description.</Drawer.Description>
 *       <Drawer.Close />
 *     </Drawer.Header>
 *     <Drawer.Body>
 *       Content goes here
 *     </Drawer.Body>
 *     <Drawer.Footer>
 *       <Button>Save</Button>
 *     </Drawer.Footer>
 *   </Drawer.Content>
 * </Drawer>
 */
const DrawerRoot: DrawerComponent = ({
  direction = 'right',
  size = '1/3',
  open,
  defaultOpen,
  onOpenChange,
  children,
}) => {
  // Generate unique IDs for ARIA
  const uniqueId = useId();
  const titleId = `drawer-title-${uniqueId}`;
  const descriptionId = `drawer-description-${uniqueId}`;

  // Context value for sub-components
  const contextValue: DrawerContextValue = useMemo(
    () => ({
      direction,
      size,
      titleId,
      descriptionId,
    }),
    [direction, size, titleId, descriptionId],
  );

  return (
    <DrawerContext.Provider value={contextValue}>
      <Dialog.Root open={open} defaultOpen={defaultOpen} onOpenChange={onOpenChange}>
        {children}
      </Dialog.Root>
    </DrawerContext.Provider>
  );
};

// Attach sub-components
DrawerRoot.displayName = 'Drawer';
DrawerRoot.Trigger = DrawerTrigger;
DrawerRoot.Content = DrawerContent;
DrawerRoot.Header = DrawerHeader;
DrawerRoot.Title = DrawerTitle;
DrawerRoot.Description = DrawerDescription;
DrawerRoot.Body = DrawerBody;
DrawerRoot.Footer = DrawerFooter;
DrawerRoot.Close = DrawerClose;

export const Drawer = DrawerRoot;
