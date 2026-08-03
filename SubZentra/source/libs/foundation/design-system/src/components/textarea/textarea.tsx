/**
 * Textarea component
 * @module components/textarea
 */

import React from 'react';

import { useTheme } from '../../theme';
import type { OIComponentRef } from '../../types';
import type { TextareaComponent, TextareaProps } from './types';
import { textareaDefaultTheme } from './types';

/**
 * Textarea component
 *
 * A multi-line text input with support for validation states and form integration.
 *
 * @example
 * // Basic usage
 * <Textarea placeholder="Enter your message" />
 *
 * @example
 * // With validation
 * <Textarea invalid aria-describedby="message-error" />
 * <span id="message-error">Message is required</span>
 *
 * @example
 * // With rows
 * <Textarea rows={6} />
 */
export const Textarea: TextareaComponent = React.forwardRef<HTMLTextAreaElement, TextareaProps>(
  function Textarea(
    {
      className,
      ozid,
      size = 'md',
      disabled,
      invalid,
      readOnly,
      'aria-describedby': ariaDescribedBy,
      rows = 3,
      ...rest
    },
    ref: OIComponentRef<'textarea'>,
  ) {
    const theme = useTheme('textarea', textareaDefaultTheme);

    return (
      <textarea
        ref={ref}
        className={theme.root({ className, size, disabled, invalid, readOnly })}
        data-ozid={ozid}
        disabled={disabled}
        readOnly={readOnly}
        aria-invalid={invalid || undefined}
        aria-describedby={ariaDescribedBy}
        rows={rows}
        {...rest}
      />
    );
  },
) as TextareaComponent;

Textarea.displayName = 'Textarea';
