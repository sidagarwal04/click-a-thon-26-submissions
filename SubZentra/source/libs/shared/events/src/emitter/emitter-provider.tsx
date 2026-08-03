import { useState, type ReactElement, type ReactNode } from 'react';

import { createEmitter } from './create-emitter';
import { EmitterContext } from './emitter-context';
import type { EventMap, TypedEmitter } from './types';

export interface EmitterProviderProps<TEvents extends EventMap = Record<string, unknown[]>> {
  emitter?: TypedEmitter<TEvents>;
  children: ReactNode;
}

export const EmitterProvider = <TEvents extends EventMap = Record<string, unknown[]>>({
  emitter,
  children,
}: EmitterProviderProps<TEvents>): ReactElement => {
  // Lazily created once and never reassigned. useState's initialiser runs on
  // the first render only, which is what the ref was imitating — but a ref
  // written during render is unsound under concurrent rendering, and this is
  // read during render.
  const [fallbackEmitter] = useState<TypedEmitter<TEvents>>(() =>
    createEmitter<TEvents>(),
  );

  const contextEmitter = emitter ?? fallbackEmitter;

  return (
    <EmitterContext.Provider value={contextEmitter as unknown as TypedEmitter<EventMap>}>
      {children}
    </EmitterContext.Provider>
  );
};
