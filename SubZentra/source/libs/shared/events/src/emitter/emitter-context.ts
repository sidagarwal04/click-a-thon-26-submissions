import { createContext } from 'react';

import type { EventMap, TypedEmitter } from './types';

export const EmitterContext = createContext<TypedEmitter<EventMap> | null>(null);
