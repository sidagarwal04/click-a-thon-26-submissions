import { describe, expect, it, vi } from 'vitest';

import { createEmitter } from './create-emitter';

type AppEvents = {
  'toast:show': [message: string, level: 'info' | 'error'];
  'modal:open': [id: string];
};

describe('createEmitter', () => {
  it('emits typed events and calls subscribers', () => {
    const emitter = createEmitter<AppEvents>();
    const handleToast = vi.fn();

    emitter.on('toast:show', handleToast);
    const handleEmit = emitter.emit('toast:show', 'Saved', 'info');

    expect(handleEmit).toBe(true);
    expect(handleToast).toHaveBeenCalledTimes(1);
    expect(handleToast).toHaveBeenCalledWith('Saved', 'info');
  });

  it('supports once and off listener behavior', () => {
    const emitter = createEmitter<AppEvents>();
    const handleOpen = vi.fn();

    emitter.once('modal:open', handleOpen);
    emitter.emit('modal:open', 'settings');
    emitter.emit('modal:open', 'billing');

    expect(handleOpen).toHaveBeenCalledTimes(1);
    expect(handleOpen).toHaveBeenCalledWith('settings');

    const handleToast = vi.fn();
    emitter.on('toast:show', handleToast);
    emitter.off('toast:show', handleToast);

    emitter.emit('toast:show', 'No listener', 'error');
    expect(handleToast).not.toHaveBeenCalled();
  });
});
