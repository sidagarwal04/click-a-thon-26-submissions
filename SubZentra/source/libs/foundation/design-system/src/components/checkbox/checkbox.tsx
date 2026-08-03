/**
 * Checkbox component using Base UI
 * @module components/checkbox
 */
import React from 'react';

import { Checkbox as CheckboxPrimitive } from '@base-ui/react/checkbox';

import { Icon } from '@open-zentra/foundation-icons';

import { useTheme } from '../../theme';
import type { CheckboxComponent, CheckboxProps } from './types';
import { checkboxDefaultTheme } from './types';

/**
 * Check icon for checked state
 */
const CheckIcon = () => <Icon name="check" size="xs" />;

/**
 * Minus icon for indeterminate state
 */
const MinusIcon = () => <Icon name="minus" size="xs" />;

/**
 * Checkbox component
 *
 * An accessible checkbox component built on Base UI primitives.
 *
 * @example
 * // Basic usage
 * <Checkbox />
 *
 * @example
 * // Controlled
 * <Checkbox checked={checked} onCheckedChange={setChecked} />
 *
 * @example
 * // With label
 * <label className="flex items-center gap-2">
 *   <Checkbox id="terms" />
 *   <span>Accept terms and conditions</span>
 * </label>
 *
 * @example
 * // Indeterminate state
 * <Checkbox indeterminate />
 */
export const Checkbox: CheckboxComponent = React.forwardRef<HTMLSpanElement, CheckboxProps>(
  function Checkbox(
    {
      className,
      ozid,
      size = 'md',
      disabled,
      checked,
      defaultChecked,
      onCheckedChange,
      indeterminate,
      required,
      name,
      id,
      ...rest
    },
    ref,
  ) {
    const theme = useTheme('checkbox', checkboxDefaultTheme);

    return (
      // rest first: caller-supplied lang, aria and data attributes reach the
      // root, but never at the cost of the props managed here.
      <CheckboxPrimitive.Root
        {...rest}
        ref={ref}
        className={theme.root({
          className,
          size,
          disabled,
          checked: !!checked,
          indeterminate: !!indeterminate,
        })}
        data-ozid={ozid}
        disabled={disabled}
        checked={checked === 'indeterminate' ? false : checked}
        defaultChecked={defaultChecked}
        onCheckedChange={onCheckedChange}
        indeterminate={indeterminate || checked === 'indeterminate'}
        required={required}
        name={name}
        id={id}
      >
        <CheckboxPrimitive.Indicator
          className={theme.indicator?.({ size }) ?? ''}
          data-ozid={ozid ? `${ozid}__indicator` : undefined}
        >
          {indeterminate || checked === 'indeterminate' ? <MinusIcon /> : <CheckIcon />}
        </CheckboxPrimitive.Indicator>
      </CheckboxPrimitive.Root>
    );
  },
) as CheckboxComponent;

Checkbox.displayName = 'Checkbox';
