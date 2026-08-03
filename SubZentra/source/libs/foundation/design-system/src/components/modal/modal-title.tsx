/**
 * Modal.Title sub-component
 * @module components/modal
 */
import React from 'react';

import { Dialog } from '@base-ui/react/dialog';

import { useTheme } from '../../theme';
import { useModalContext } from './modal.context';
import type { ModalTitleProps } from './types';
import { modalDefaultTheme } from './types';

/**
 * Modal.Title component
 *
 * Title text for the modal. Connected to Dialog.Title for accessibility.
 */
export const ModalTitle: React.FC<ModalTitleProps> = ({ children, className, ozid }) => {
  const theme = useTheme('modal', modalDefaultTheme);
  const { titleId } = useModalContext();

  return (
    <Dialog.Title
      id={titleId}
      className={theme.title?.({ className }) ?? className}
      data-ozid={ozid}
      data-slot="title"
    >
      {children}
    </Dialog.Title>
  );
};

ModalTitle.displayName = 'Modal.Title';
