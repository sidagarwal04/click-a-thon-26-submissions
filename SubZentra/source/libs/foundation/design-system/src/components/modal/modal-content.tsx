/**
 * Modal.Content sub-component
 * @module components/modal
 */
import React from 'react';

import { Dialog } from '@base-ui/react/dialog';

import { useTheme } from '../../theme';
import { useModalContext } from './modal.context';
import type { ModalContentProps } from './types';
import { modalDefaultTheme } from './types';

/**
 * Modal.Content component
 *
 * Container for the modal content. Renders backdrop and popup.
 */
export const ModalContent = React.forwardRef<HTMLDivElement, ModalContentProps>(
  function ModalContent({ children, className, ozid, ...rest }, ref) {
    const theme = useTheme('modal', modalDefaultTheme);
    const { size, fillContainer, fitContent, titleId, descriptionId } = useModalContext();

    return (
      <Dialog.Portal>
        <Dialog.Backdrop
          className={theme.backdrop?.({}) ?? ''}
          data-ozid={ozid ? `${ozid}__backdrop` : undefined}
        />
        {/* rest first: caller-supplied lang, aria and data attributes reach the
            root, but never at the cost of the props this component manages. */}
        <Dialog.Popup
          {...rest}
          ref={ref}
          className={theme.popup?.({ className, size, fillContainer, fitContent }) ?? className}
          data-ozid={ozid}
          data-slot="content"
          aria-labelledby={rest['aria-labelledby'] ?? titleId}
          aria-describedby={rest['aria-describedby'] ?? descriptionId}
        >
          {/* `flex-1 min-h-0`, not `h-full`. The popup carries a max-height but
              no definite height, so `height: 100%` here has nothing to resolve
              against and collapses to auto — the column then grows past the
              popup and a long modal spills off the screen instead of scrolling.
              `min-h-0` is what lets this column shrink below its content so the
              `overflow-auto` on Modal.Body becomes the scroll container. */}
          <div className="flex min-h-0 flex-1 flex-col">{children}</div>
        </Dialog.Popup>
      </Dialog.Portal>
    );
  },
);

ModalContent.displayName = 'Modal.Content';
