/**
 * RadioGroup context for compound component pattern
 * @module components/radio-group/context
 */
import React, { createContext, useContext } from 'react';

import type { RadioGroupVariants } from './types';

interface RadioGroupContextValue {
  size: (typeof RadioGroupVariants.size)[number];
  disabled?: boolean;
  ozid?: string;
}

const RadioGroupContext = createContext<RadioGroupContextValue | null>(null);

export function RadioGroupProvider({
  children,
  value,
}: {
  children: React.ReactNode;
  value: RadioGroupContextValue;
}) {
  return <RadioGroupContext.Provider value={value}>{children}</RadioGroupContext.Provider>;
}

export function useRadioGroupContext() {
  const context = useContext(RadioGroupContext);
  if (!context) {
    throw new Error('useRadioGroupContext must be used within a RadioGroupProvider');
  }
  return context;
}
