/**
 * RadioGroupItem component using Base UI
 * @module components/radio-group/item
 */
import React from 'react';

import { Radio } from '@base-ui/react/radio';

import { useTheme } from '../../theme';
import { useRadioGroupContext } from './radio-group.context';
import type { RadioGroupItemComponent, RadioGroupItemProps } from './types';
import { radioGroupDefaultTheme } from './types';

/**
 * Circle indicator for checked state
 */
const CircleIndicator = () => <div className="h-2 w-2 rounded-full bg-primary-foreground" />;

/**
 * RadioGroupItem component
 *
 * Individual radio option within a RadioGroup.
 *
 * @example
 * <RadioGroup.Item value="option1" id="option1" />
 * <label htmlFor="option1">Option 1</label>
 */
export const RadioGroupItem: RadioGroupItemComponent = React.forwardRef<
  HTMLButtonElement,
  RadioGroupItemProps
>(function RadioGroupItem(
  { className, ozid: propOzid, disabled, value, id },
  ref: React.ForwardedRef<HTMLButtonElement>,
) {
  const { size, disabled: groupDisabled, ozid: contextOzid } = useRadioGroupContext();
  const theme = useTheme('radioGroup', radioGroupDefaultTheme);
  const isDisabled = disabled || groupDisabled;
  const ozid = propOzid ?? (contextOzid ? `${contextOzid}__item-${value}` : undefined);

  return (
    <Radio.Root
      ref={ref}
      className={theme.item?.({ className, size }) ?? ''}
      data-ozid={ozid}
      disabled={isDisabled}
      value={value}
      id={id}
    >
      <Radio.Indicator
        className={theme.indicator?.({ size }) ?? ''}
        data-ozid={ozid ? `${ozid}__indicator` : undefined}
      >
        <CircleIndicator />
      </Radio.Indicator>
    </Radio.Root>
  );
}) as RadioGroupItemComponent;

RadioGroupItem.displayName = 'RadioGroupItem';
