/**
 * SelectTrigger component
 * @module components/select/trigger
 */
import React from 'react';

import { Select as SelectPrimitive } from '@base-ui/react/select';

import { Icon } from '@open-zentra/foundation-icons';

import { useTheme } from '../../theme';
import { useSelectContext } from './select.context';
import type { SelectTriggerComponent, SelectTriggerProps } from './types';
import { selectDefaultTheme } from './types';

/**
 * SelectTrigger component
 *
 * The trigger button that opens the select dropdown.
 */
export const SelectTrigger: SelectTriggerComponent = React.forwardRef<
  HTMLButtonElement,
  SelectTriggerProps
>(function SelectTrigger(
  { className, ozid: propOzid, children, placeholder, ...rest },
  ref: React.ForwardedRef<HTMLButtonElement>,
) {
  const { size, disabled, ozid: contextOzid } = useSelectContext();
  const theme = useTheme('select', selectDefaultTheme);
  const ozid = propOzid ?? (contextOzid ? `${contextOzid}__trigger` : undefined);

  return (
    <SelectPrimitive.Trigger
      ref={ref}
      className={theme.trigger?.({ className, size }) ?? ''}
      data-ozid={ozid}
      disabled={disabled}
      {...rest}
    >
      <SelectPrimitive.Value placeholder={placeholder}>{children}</SelectPrimitive.Value>
      <SelectPrimitive.Icon>
        <Icon name="chevron_down" size="sm" className="opacity-50" />
      </SelectPrimitive.Icon>
    </SelectPrimitive.Trigger>
  );
}) as SelectTriggerComponent;

SelectTrigger.displayName = 'SelectTrigger';
