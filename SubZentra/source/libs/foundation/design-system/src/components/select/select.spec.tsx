import { describeComponent, splitRootProps } from '../../test/describe-component';
import { Select, SelectModifiers, SelectVariants } from './index';

describeComponent(
  <Select>
    <div>Select content</div>
  </Select>,
  {
    name: 'Select',
    rootInstanceOf: window.HTMLDivElement,
    variants: SelectVariants,
    modifiers: SelectModifiers,
    shouldSupportPolymorphism: false,
    shouldSupportForwardRef: true,
    // <Select> renders a context provider and no DOM node; Content is the
    // element that reaches the document and is styled from the content slot.
    rootSlot: 'content',
    renderRoot: (rootProps) => {
      const { domProps, ownProps } = splitRootProps(rootProps);
      return (
        <Select open {...ownProps}>
          <Select.Content {...domProps}>Select content</Select.Content>
        </Select>
      );
    },
  },
);
