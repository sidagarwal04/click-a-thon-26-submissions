import { describeComponent, splitRootProps } from '../../test/describe-component';
import { Popover, PopoverModifiers, PopoverVariants } from './index';

describeComponent(
  <Popover>
    <div>Popover content</div>
  </Popover>,
  {
    name: 'Popover',
    rootInstanceOf: window.HTMLDivElement,
    variants: PopoverVariants,
    modifiers: PopoverModifiers,
    shouldSupportPolymorphism: false,
    shouldSupportForwardRef: true,
    // <Popover> renders a context provider and no DOM node; Content is the
    // element that reaches the document and is styled from the popup slot.
    rootSlot: 'popup',
    renderRoot: (rootProps) => {
      const { domProps, ownProps } = splitRootProps(rootProps);
      return (
        <Popover open {...ownProps}>
          <Popover.Content {...domProps}>Popover content</Popover.Content>
        </Popover>
      );
    },
  },
);
