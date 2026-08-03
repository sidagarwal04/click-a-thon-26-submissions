/**
 * Modal.Close sub-component
 * @module components/modal
 */
import React from 'react';

import { Dialog } from '@base-ui/react/dialog';

import { Icon } from '@open-zentra/foundation-icons';

import { useTheme } from '../../theme';
import type { ModalCloseProps } from './types';
import { modalDefaultTheme } from './types';

/**
 * Modal.Close component
 *
 * Button that closes the modal. Can be used standalone or wrap custom content.
 */
export const ModalClose: React.FC<ModalCloseProps> = ({ children, className, ozid, ...rest }) => {
  const theme = useTheme('modal', modalDefaultTheme);

  return (
    <Dialog.Close
      className={className || theme.close?.({}) || ''}
      data-ozid={ozid}
      data-slot="close"
      aria-label="Close"
      {...rest}
    >
      {children || <Icon name="x" size="sm" />}
    </Dialog.Close>
  );
};

ModalClose.displayName = 'Modal.Close';
