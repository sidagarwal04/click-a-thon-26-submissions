import { beforeEach, describe, expect, it, vi } from 'vitest';

import { SyncCoordinator } from './index';

const networkUnsubscribers: Array<() => void> = [];
const crossTabUnsubscribers: Array<() => void> = [];

const mockNetworkMonitor = {
  isOnline: false,
  start: vi.fn(async () => undefined),
  stop: vi.fn(() => undefined),
  subscribe: vi.fn((listener: (status: { isOnline: boolean }) => void) => {
    const unsubscribe = vi.fn(() => undefined);
    networkUnsubscribers.push(unsubscribe);
    listener({ isOnline: false });
    return unsubscribe;
  }),
  checkConnectivity: vi.fn(async () => true),
  disposeAsync: vi.fn(async () => undefined),
};

const mockQueueManager = {
  getStats: vi.fn(async () => ({
    pending: 0,
    inProgress: 0,
    failed: 0,
    offlineQueued: 0,
    total: 0,
  })),
  markAllPending: vi.fn(async () => 0),
  markAllOfflineQueued: vi.fn(async () => 0),
  dispose: vi.fn(() => undefined),
};

const mockConflictResolver = {
  dispose: vi.fn(() => undefined),
};

const mockCrossTabManager = {
  id: 'tab-1',
  isLeader: true,
  start: vi.fn(() => undefined),
  stop: vi.fn(() => undefined),
  dispose: vi.fn(() => undefined),
  subscribe: vi.fn(() => {
    const unsubscribe = vi.fn(() => undefined);
    crossTabUnsubscribers.push(unsubscribe);
    return unsubscribe;
  }),
  notifyOnline: vi.fn(() => undefined),
  notifyOffline: vi.fn(() => undefined),
  notifySyncStarted: vi.fn(() => undefined),
  notifySyncCompleted: vi.fn(() => undefined),
  invalidateQueries: vi.fn(() => undefined),
};

const mockHttpMutationAdapter = {
  createMutationExecutor: vi.fn(() => vi.fn()),
  dispose: vi.fn(() => undefined),
};

const mockRealtimeBridge = {
  apply: vi.fn(() => undefined),
  dispose: vi.fn(() => undefined),
};

vi.mock('../network/index', () => ({
  createNetworkMonitor: vi.fn(() => mockNetworkMonitor),
}));

vi.mock('../queue/manager', () => ({
  createQueueManager: vi.fn(() => mockQueueManager),
}));

vi.mock('../conflicts/resolver', () => ({
  createConflictResolver: vi.fn(() => mockConflictResolver),
}));

vi.mock('../cross-tab/manager', () => ({
  createCrossTabManager: vi.fn(() => mockCrossTabManager),
}));

vi.mock('../http/adapter', () => ({
  createHttpMutationAdapter: vi.fn(() => mockHttpMutationAdapter),
}));

vi.mock('../realtime/bridge', () => ({
  createRealtimeEventBridge: vi.fn(() => mockRealtimeBridge),
}));

describe('SyncCoordinator lifecycle', () => {
  beforeEach(() => {
    networkUnsubscribers.length = 0;
    crossTabUnsubscribers.length = 0;
    mockNetworkMonitor.isOnline = false;

    mockNetworkMonitor.start.mockClear();
    mockNetworkMonitor.stop.mockClear();
    mockNetworkMonitor.subscribe.mockClear();
    mockNetworkMonitor.disposeAsync.mockClear();

    mockQueueManager.getStats.mockClear();
    mockQueueManager.markAllPending.mockClear();
    mockQueueManager.markAllOfflineQueued.mockClear();
    mockQueueManager.dispose.mockClear();

    mockConflictResolver.dispose.mockClear();
    mockCrossTabManager.start.mockClear();
    mockCrossTabManager.stop.mockClear();
    mockCrossTabManager.dispose.mockClear();
    mockCrossTabManager.subscribe.mockClear();
    mockHttpMutationAdapter.dispose.mockClear();
    mockRealtimeBridge.dispose.mockClear();
  });

  it('does not leak subscriptions across start-stop cycles', async () => {
    const coordinator = new SyncCoordinator({
      queryClient: { invalidateQueries: vi.fn() } as never,
      axiosInstance: { request: vi.fn(), defaults: {} } as never,
      autoStart: false,
      enableCrossTab: true,
      debug: false,
    });

    await coordinator.start();
    coordinator.stop();
    await coordinator.start();
    coordinator.stop();

    expect(mockNetworkMonitor.subscribe).toHaveBeenCalledTimes(2);
    expect(networkUnsubscribers).toHaveLength(2);
    expect(networkUnsubscribers[0]).toHaveBeenCalledTimes(1);
    expect(networkUnsubscribers[1]).toHaveBeenCalledTimes(1);

    expect(mockCrossTabManager.subscribe).toHaveBeenCalledTimes(8);
    expect(crossTabUnsubscribers).toHaveLength(8);
    for (const unsubscribe of crossTabUnsubscribers) {
      expect(unsubscribe).toHaveBeenCalledTimes(1);
    }

    await coordinator.disposeAsync();
  });
});
