import { describeComponent, splitRootProps } from '../../test/describe-component';
import { Menu, MenuModifiers, MenuVariants } from './index';

describeComponent(
  <Menu>
    <div>Menu content</div>
  </Menu>,
  {
    name: 'Menu',
    rootInstanceOf: window.HTMLDivElement,
    variants: MenuVariants,
    modifiers: MenuModifiers,
    shouldSupportPolymorphism: false,
    shouldSupportForwardRef: true,
    // <Menu> renders a context provider and no DOM node; Content is the element
    // that reaches the document and is styled from the popup slot.
    rootSlot: 'popup',
    renderRoot: (rootProps) => {
      const { domProps, ownProps } = splitRootProps(rootProps);
      return (
        <Menu open {...ownProps}>
          <Menu.Content {...domProps}>Menu content</Menu.Content>
        </Menu>
      );
    },
  },
);
