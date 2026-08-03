/**
 * Modal component
 * @module components/modal
 */
import { useId, useMemo } from 'react';

import { Dialog } from '@base-ui/react/dialog';

import { ModalBody } from './modal-body';
import { ModalClose } from './modal-close';
import { ModalContent } from './modal-content';
import { ModalDescription } from './modal-description';
import { ModalFooter } from './modal-footer';
import { ModalHeader } from './modal-header';
import { ModalTitle } from './modal-title';
import { ModalTrigger } from './modal-trigger';
import { ModalContext } from './modal.context';
import type { ModalComponent, ModalContextValue } from './types';

/**
 * Modal component
 *
 * A dialog overlay that requires user interaction. Built on Base UI Dialog primitives.
 *
 * @example
 * <Modal>
 *   <Modal.Trigger asChild>
 *     <Button>Open Modal</Button>
 *   </Modal.Trigger>
 *   <Modal.Content>
 *     <Modal.Header>
 *       <Modal.Title>Modal Title</Modal.Title>
 *       <Modal.Description>Modal description text.</Modal.Description>
 *       <Modal.Close />
 *     </Modal.Header>
 *     <Modal.Body>
 *       Content goes here
 *     </Modal.Body>
 *     <Modal.Footer>
 *       <Modal.Close asChild>
 *         <Button variant="outline">Cancel</Button>
 *       </Modal.Close>
 *       <Button>Save</Button>
 *     </Modal.Footer>
 *   </Modal.Content>
 * </Modal>
 */
const ModalRoot: ModalComponent = ({
  size = '720',
  // Defaulted to `false` rather than left undefined. The theme resolver only
  // emits a modifier branch for an actual boolean, so an undefined
  // `fillContainer` skipped *both* branches — and the `false` branch is what
  // carries the popup's `max-h-[calc(100vh-4rem)]`. The modal therefore had no
  // height cap at all, and a long one grew past the viewport with nothing to
  // scroll.
  fillContainer = false,
  fitContent = false,
  open,
  defaultOpen,
  onOpenChange,
  children,
}) => {
  // Generate unique IDs for ARIA
  const uniqueId = useId();
  const titleId = `modal-title-${uniqueId}`;
  const descriptionId = `modal-description-${uniqueId}`;

  // Context value for sub-components
  const contextValue: ModalContextValue = useMemo(
    () => ({
      size,
      fillContainer,
      fitContent,
      titleId,
      descriptionId,
    }),
    [size, fillContainer, fitContent, titleId, descriptionId],
  );

  return (
    <ModalContext.Provider value={contextValue}>
      <Dialog.Root open={open} defaultOpen={defaultOpen} onOpenChange={onOpenChange}>
        {children}
      </Dialog.Root>
    </ModalContext.Provider>
  );
};

// Attach sub-components
ModalRoot.displayName = 'Modal';
ModalRoot.Trigger = ModalTrigger;
ModalRoot.Content = ModalContent;
ModalRoot.Header = ModalHeader;
ModalRoot.Title = ModalTitle;
ModalRoot.Description = ModalDescription;
ModalRoot.Body = ModalBody;
ModalRoot.Footer = ModalFooter;
ModalRoot.Close = ModalClose;

export const Modal = ModalRoot;
