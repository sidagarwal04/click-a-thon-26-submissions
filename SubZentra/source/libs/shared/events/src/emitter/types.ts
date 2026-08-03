import type EventEmitter from 'eventemitter3';

export type EventMap = EventEmitter.ValidEventTypes;
export type TypedEmitter<TEvents extends EventMap = Record<string, unknown[]>> =
  EventEmitter<TEvents>;
