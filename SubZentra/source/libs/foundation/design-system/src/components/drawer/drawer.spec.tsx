import { describeComponent, splitRootProps } from '../../test/describe-component';
import { Drawer, DrawerModifiers, DrawerVariants } from './index';

describeComponent(
  <Drawer open>
    <div>Drawer content</div>
  </Drawer>,
  {
    name: 'Drawer',
    rootInstanceOf: window.HTMLDivElement,
    variants: DrawerVariants,
    modifiers: DrawerModifiers,
    shouldSupportPolymorphism: false,
    shouldSupportForwardRef: true,
    // <Drawer> renders a context provider and no DOM node; Content is the
    // element that reaches the document and is styled from the popup slot.
    rootSlot: 'popup',
    renderRoot: (rootProps) => {
      const { domProps, ownProps } = splitRootProps(rootProps);
      return (
        <Drawer open {...ownProps}>
          <Drawer.Content {...domProps}>Drawer content</Drawer.Content>
        </Drawer>
      );
    },
  },
);
