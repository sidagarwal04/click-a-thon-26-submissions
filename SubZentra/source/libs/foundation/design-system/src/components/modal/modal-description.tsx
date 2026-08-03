/**
 * Modal.Description sub-component
 * @module components/modal
 */
import React from 'react';

import { Dialog } from '@base-ui/react/dialog';

import { useTheme } from '../../theme';
import { useModalContext } from './modal.context';
import type { ModalDescriptionProps } from './types';
import { modalDefaultTheme } from './types';

/**
 * Modal.Description component
 *
 * Description text for the modal. Connected to Dialog.Description for accessibility.
 */
export const ModalDescription: React.FC<ModalDescriptionProps> = ({
  children,
  className,
  ozid,
}) => {
  const theme = useTheme('modal', modalDefaultTheme);
  const { descriptionId } = useModalContext();

  return (
    <Dialog.Description
      id={descriptionId}
      className={theme.description?.({ className }) ?? className}
      data-ozid={ozid}
      data-slot="description"
    >
      {children}
    </Dialog.Description>
  );
};

ModalDescription.displayName = 'Modal.Description';
