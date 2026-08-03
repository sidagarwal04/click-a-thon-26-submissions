/**
 * Modal.Footer sub-component
 * @module components/modal
 */
import React from 'react';

import { useTheme } from '../../theme';
import type { ModalFooterProps } from './types';
import { modalDefaultTheme } from './types';

/**
 * Modal.Footer component
 *
 * Container for action buttons at the bottom of the modal.
 */
export const ModalFooter: React.FC<ModalFooterProps> = ({ children, className, ozid }) => {
  const theme = useTheme('modal', modalDefaultTheme);

  return (
    <div className={theme.footer?.({ className }) ?? className} data-ozid={ozid} data-slot="footer">
      {children}
    </div>
  );
};

ModalFooter.displayName = 'Modal.Footer';
