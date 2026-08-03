import { describeComponent, splitRootProps } from '../../test/describe-component';
import { Modal, ModalModifiers, ModalVariants } from './index';

describeComponent(
  <Modal open>
    <div>Modal content</div>
  </Modal>,
  {
    name: 'Modal',
    rootInstanceOf: window.HTMLDivElement,
    variants: ModalVariants,
    modifiers: ModalModifiers,
    shouldSupportPolymorphism: false,
    shouldSupportForwardRef: true,
    // <Modal> itself renders a context provider and no DOM node, so the
    // root-element contract is applied to Content, which is the element that
    // actually reaches the document. Size and the modifiers stay on <Modal>,
    // which is where the component's API takes them; Content reads them from
    // context and styles its popup slot from them.
    rootSlot: 'popup',
    renderRoot: (rootProps) => {
      const { domProps, ownProps } = splitRootProps(rootProps);
      return (
        <Modal open {...ownProps}>
          <Modal.Content {...domProps}>Modal content</Modal.Content>
        </Modal>
      );
    },
  },
);
