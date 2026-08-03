import { describe, expect, it, vi } from 'vitest';

import { createUnauthenticatedAuthState } from '../../kernel';
import { createManagedAuthAdapter } from './managed-auth-adapter';

describe('createManagedAuthAdapter', () => {
  it('notifies state and scope subscribers when the snapshot changes', () => {
    const adapter = createManagedAuthAdapter('test');
    const stateListener = vi.fn();
    const scopeListener = vi.fn();

    adapter.subscribe(stateListener);
    adapter.subscribeScope(scopeListener);

    const nextState = createUnauthenticatedAuthState('test');
    adapter.setSnapshot(nextState);

    expect(stateListener).toHaveBeenLastCalledWith(nextState);
    expect(scopeListener).toHaveBeenLastCalledWith(nextState.scope);
  });

  it('delegates transport resolution to the active action set', async () => {
    const adapter = createManagedAuthAdapter('test');

    adapter.setActions({
      getTransport: async () => ({ kind: 'bearer', token: 'session-token' }),
    });

    await expect(adapter.getAccessToken()).resolves.toBeNull();
    await expect(adapter.getTransport()).resolves.toEqual({
      kind: 'bearer',
      token: 'session-token',
    });
  });
});
