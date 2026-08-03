import { expectTypeOf, it } from 'vitest';

import { createEmitter } from './create-emitter';

type AppEvents = {
  'toast:show': [message: string, level: 'info' | 'error'];
  'modal:open': [id: string];
};

it('preserves event payload types', () => {
  const emitter = createEmitter<AppEvents>();

  emitter.on('toast:show', (message, level) => {
    expectTypeOf(message).toEqualTypeOf<string>();
    expectTypeOf(level).toEqualTypeOf<'info' | 'error'>();
  });

  emitter.emit('modal:open', 'settings');

  // @ts-expect-error invalid event name should fail typing
  emitter.emit('unknown:event', 'payload');

  // @ts-expect-error wrong payload arity should fail typing
  emitter.emit('modal:open', 'settings', true);
});
