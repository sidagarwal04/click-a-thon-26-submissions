import axios from 'axios';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { NetworkStatusMonitor } from './index';

const createFakeDatabase = () => ({
  syncState: {
    get: vi.fn(async () => undefined),
    put: vi.fn(async () => undefined),
  },
});

describe('NetworkStatusMonitor lifecycle', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('detaches and reattaches browser listeners across stop/start cycles', async () => {
    const addSpy = vi.spyOn(window, 'addEventListener');
    const removeSpy = vi.spyOn(window, 'removeEventListener');
    vi.spyOn(axios, 'head').mockResolvedValue({ status: 200 } as never);

    const fakeDatabase = createFakeDatabase();

    const monitor = new NetworkStatusMonitor({
      database: fakeDatabase as never,
      healthCheckInterval: 0,
      healthCheckTimeout: 100,
      debug: false,
    });

    await monitor.start();
    monitor.stop();
    await monitor.start();
    monitor.stop();

    const addOnlineCalls = addSpy.mock.calls.filter((call) => call[0] === 'online');
    const addOfflineCalls = addSpy.mock.calls.filter((call) => call[0] === 'offline');
    const removeOnlineCalls = removeSpy.mock.calls.filter((call) => call[0] === 'online');
    const removeOfflineCalls = removeSpy.mock.calls.filter((call) => call[0] === 'offline');

    expect(addOnlineCalls).toHaveLength(2);
    expect(addOfflineCalls).toHaveLength(2);
    expect(removeOnlineCalls).toHaveLength(2);
    expect(removeOfflineCalls).toHaveLength(2);

    await monitor.disposeAsync();
  });
});
