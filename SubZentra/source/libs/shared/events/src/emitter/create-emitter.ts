import EventEmitter from 'eventemitter3';

import type { EventMap, TypedEmitter } from './types';

export const createEmitter = <
  TEvents extends EventMap = Record<string, unknown[]>,
>(): TypedEmitter<TEvents> => new EventEmitter<TEvents>();
