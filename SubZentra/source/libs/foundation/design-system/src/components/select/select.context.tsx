/**
 * Select context for compound component pattern
 * @module components/select/context
 */
import React, { createContext, useContext } from 'react';

import type { SelectVariants } from './types';

interface SelectContextValue {
  size: (typeof SelectVariants.size)[number];
  disabled?: boolean;
  ozid?: string;
}

const SelectContext = createContext<SelectContextValue | null>(null);

export function SelectProvider({
  children,
  value,
}: {
  children: React.ReactNode;
  value: SelectContextValue;
}) {
  return <SelectContext.Provider value={value}>{children}</SelectContext.Provider>;
}

export function useSelectContext() {
  const context = useContext(SelectContext);
  if (!context) {
    throw new Error('useSelectContext must be used within a SelectProvider');
  }
  return context;
}
