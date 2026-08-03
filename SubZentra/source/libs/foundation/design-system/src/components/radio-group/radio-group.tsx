/**
 * RadioGroup component using Base UI
 * @module components/radio-group
 */
import React from 'react';

import { RadioGroup as RadioGroupPrimitive } from '@base-ui/react/radio-group';

import { useTheme } from '../../theme';
import { RadioGroupItem } from './radio-group-item';
import { RadioGroupProvider } from './radio-group.context';
import type { RadioGroupComponent, RadioGroupProps } from './types';
import { radioGroupDefaultTheme } from './types';

/**
 * RadioGroup component
 *
 * An accessible radio group component built on Base UI primitives.
 * Uses compound component pattern with RadioGroup.Item.
 *
 * @example
 * // Basic usage
 * <RadioGroup defaultValue="option1">
 *   <div className="flex items-center gap-2">
 *     <RadioGroup.Item value="option1" id="option1" />
 *     <label htmlFor="option1">Option 1</label>
 *   </div>
 *   <div className="flex items-center gap-2">
 *     <RadioGroup.Item value="option2" id="option2" />
 *     <label htmlFor="option2">Option 2</label>
 *   </div>
 * </RadioGroup>
 *
 * @example
 * // Controlled
 * <RadioGroup value={value} onValueChange={setValue}>
 *   {options.map(option => (
 *     <RadioGroup.Item key={option.value} value={option.value} />
 *   ))}
 * </RadioGroup>
 */
const RadioGroupRoot: RadioGroupComponent = React.forwardRef<HTMLDivElement, RadioGroupProps>(
  function RadioGroup(
    {
      className,
      ozid,
      size = 'md',
      disabled,
      value,
      defaultValue,
      onValueChange,
      children,
      name,
      ...rest
    },
    ref: React.ForwardedRef<HTMLDivElement>,
  ) {
    const theme = useTheme('radioGroup', radioGroupDefaultTheme);

    return (
      <RadioGroupProvider value={{ size, disabled, ozid }}>
        {/* rest first: caller-supplied lang, aria and data attributes reach the
            root, but never at the cost of the props managed here. */}
        <RadioGroupPrimitive
          {...rest}
          ref={ref}
          className={theme.root({ className, size, disabled })}
          data-ozid={ozid}
          disabled={disabled}
          value={value}
          defaultValue={defaultValue}
          onValueChange={onValueChange}
          name={name}
        >
          {children}
        </RadioGroupPrimitive>
      </RadioGroupProvider>
    );
  },
) as RadioGroupComponent;

RadioGroupRoot.displayName = 'RadioGroup';

/**
 * RadioGroup compound component with Item subcomponent
 */
export const RadioGroup = Object.assign(RadioGroupRoot, {
  Item: RadioGroupItem,
});
