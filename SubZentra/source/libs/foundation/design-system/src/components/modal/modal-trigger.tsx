/**
 * Modal.Trigger sub-component
 * @module components/modal
 */
import React from 'react';

import { Dialog } from '@base-ui/react/dialog';

import type { ModalTriggerProps } from './types';

/**
 * Modal.Trigger component
 *
 * Button that opens the modal dialog.
 */
export const ModalTrigger: React.FC<ModalTriggerProps> = ({
  children,
  className,
  ozid,
  ...rest
}) => {
  return (
    <Dialog.Trigger className={className} data-ozid={ozid} data-slot="trigger" {...rest}>
      {children}
    </Dialog.Trigger>
  );
};

ModalTrigger.displayName = 'Modal.Trigger';
