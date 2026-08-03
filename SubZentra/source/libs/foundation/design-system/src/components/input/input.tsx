/**
 * Input component
 * @module components/input
 */
import React from 'react';

import { Slot } from '../../primitives/slot';
import { useTheme } from '../../theme';
import { cn } from '../../utils/cn';
import type { InputComponent, InputProps } from './types';
import { inputDefaultTheme } from './types';

/**
 * Input component
 *
 * A text input component with support for validation states, adornments,
 * and full form integration.
 *
 * @example
 * // Basic usage
 * <Input placeholder="Enter your email" />
 *
 * @example
 * // With validation
 * <Input invalid aria-describedby="email-error" />
 * <span id="email-error">Invalid email address</span>
 *
 * @example
 * // With start/end slots
 * <Input
 *   start={<SearchIcon />}
 *   end={<ClearButton />}
 * />
 *
 * @example
 * // With react-hook-form
 * <Input {...register('email')} invalid={!!errors.email} />
 */
export const Input: InputComponent = React.forwardRef<HTMLInputElement, InputProps>(function Input(
  {
    className,
    ozid,
    size = 'md',
    disabled,
    invalid,
    readOnly,
    start,
    end,
    type = 'text',
    'aria-describedby': ariaDescribedBy,
    ...rest
  },
  forwardedRef,
) {
  const theme = useTheme('input', inputDefaultTheme);

  // Adjust padding for adornments
  const inputClassName = cn(
    theme.root({ size, disabled, invalid, readOnly }),
    start && (size === 'sm' ? 'pl-8' : size === 'lg' ? 'pl-12' : 'pl-10'),
    end && (size === 'sm' ? 'pr-8' : size === 'lg' ? 'pr-12' : 'pr-10'),
    className,
  );

  return (
    <div className="relative w-full">
      {start && (
        <Slot
          baseOzid={ozid}
          className={theme.start?.({ size }) ?? ''}
          slotName="start"
          slot={start}
          component="span"
          aria-hidden="true"
        />
      )}

      <input
        ref={forwardedRef}
        type={type}
        className={inputClassName}
        data-ozid={ozid}
        disabled={disabled}
        readOnly={readOnly}
        aria-invalid={invalid || undefined}
        aria-describedby={ariaDescribedBy}
        {...rest}
      />

      {end && (
        <Slot
          baseOzid={ozid}
          className={theme.end?.({ size }) ?? ''}
          slotName="end"
          slot={end}
          component="span"
        />
      )}
    </div>
  );
}) as InputComponent;

Input.displayName = 'Input';
