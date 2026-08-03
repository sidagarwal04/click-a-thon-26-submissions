import { useContext } from 'react';

import { EmitterContext } from './emitter-context';
import type { EventMap, TypedEmitter } from './types';

export const useEmitter = <
  TEvents extends EventMap = Record<string, unknown[]>,
>(): TypedEmitter<TEvents> => {
  const emitter = useContext(EmitterContext);

  if (!emitter) {
    throw new Error('useEmitter must be used within an EmitterProvider');
  }

  return emitter as unknown as TypedEmitter<TEvents>;
};
