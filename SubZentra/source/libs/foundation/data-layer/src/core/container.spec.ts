/**
 * Tests for DataLayerContainer and createDataLayerContainer
 *
 * @module core/container.spec
 */

import type { AxiosInstance } from 'axios';

import { createDataLayerContainer, DataLayerContainer, type ContainerConfig } from './container';

// ---------------------------------------------------------------------------
// Mock helpers
// ---------------------------------------------------------------------------

const createMockDatabase = () => ({
  queries: { get: vi.fn(), set: vi.fn(), delete: vi.fn() },
  syncState: { get: vi.fn(), set: vi.fn(), getRaw: vi.fn() },
  getDatabase: vi.fn(() => ({
    tableSyncMetadata: { get: vi.fn(), put: vi.fn(), bulkGet: vi.fn() },
  })),
  startCleanup: vi.fn(),
  stopCleanup: vi.fn(),
  close: vi.fn(),
  clearAll: vi.fn(),
});

const createMockSyncCoordinator = () => ({
  subscribe: vi.fn(() => vi.fn()),
  getState: vi.fn(async () => ({
    isOnline: true,
    isSyncing: false,
    pendingMutations: 0,
    failedMutations: 0,
    lastSyncAt: null,
    isLeader: false,
  })),
  sync: vi.fn(),
  disposeAsync: vi.fn(),
  getQueueManager: vi.fn(() => ({
    enqueue: vi.fn(),
    resolveId: vi.fn((id: string) => id),
  })),
  invalidateQueries: vi.fn(),
});

// The container only ever calls `request` on the axios instance, so the mock
// stops there. The cast is what says so out loud; annotating `config` as
// ContainerConfig keeps every other field genuinely checked, including the
// websocket auth mode, which infers as a bare string without it.
const createMockAxios = () =>
  ({ request: vi.fn(), defaults: {} }) as unknown as AxiosInstance;

const createConfig = (overrides: Partial<ContainerConfig> = {}) => {
  const mockDatabase = createMockDatabase();
  const mockSyncCoordinator = createMockSyncCoordinator();

  const config: ContainerConfig = {
    axiosInstance: createMockAxios(),
    websocket: {
      url: 'wss://example.test/realtime',
      auth: {
        mode: 'ticket',
        getTicket: vi.fn(async () => 'ticket_123'),
      },
    },
    factories: {
      database: () => mockDatabase as never,
      syncCoordinator: () => mockSyncCoordinator as never,
      realtimeClient: () =>
        ({
          subscribeStatus: vi.fn(() => vi.fn()),
          subscribeMessages: vi.fn(() => vi.fn()),
          connect: vi.fn(async () => undefined),
          disconnect: vi.fn(),
          send: vi.fn(),
        } as never),
    },
    ...overrides,
  };

  return {
    config,
    mocks: { mockDatabase, mockSyncCoordinator },
  };
};

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('DataLayerContainer', () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  // 1. Construction
  describe('construction', () => {
    it('creates a container without error', () => {
      const { config } = createConfig();
      expect(() => new DataLayerContainer(config)).not.toThrow();
    });

    it('starts in uninitialized and undisposed state', () => {
      const { config } = createConfig();
      const container = new DataLayerContainer(config);

      expect(container.isInitialized).toBe(false);
      expect(container.isDisposed).toBe(false);
    });
  });

  // 2. Initialize
  describe('initialize', () => {
    it('returns dependencies after initialization', async () => {
      const { config } = createConfig();
      const container = new DataLayerContainer(config);

      const deps = await container.initialize();

      expect(deps).toBeDefined();
      expect(deps.database).toBeDefined();
      expect(deps.syncCoordinator).toBeDefined();
      expect(deps.queryClient).toBeDefined();
      expect(deps.axiosInstance).toBeDefined();
      expect(deps.realtimeClient).toBeDefined();
      expect(deps.cacheConfig).toBeDefined();
      expect(deps.tableRegistry).toBeDefined();
      expect(typeof deps.initializeAnalytics).toBe('function');
    });

    it('sets isInitialized to true after init', async () => {
      const { config } = createConfig();
      const container = new DataLayerContainer(config);

      await container.initialize();

      expect(container.isInitialized).toBe(true);
    });

    it('calls database.startCleanup during initialization', async () => {
      const { config, mocks } = createConfig();
      const container = new DataLayerContainer(config);

      await container.initialize();

      expect(mocks.mockDatabase.startCleanup).toHaveBeenCalledOnce();
    });

    it('returns duckdbRouter as null (lazy analytics)', async () => {
      const { config } = createConfig();
      const container = new DataLayerContainer(config);

      const deps = await container.initialize();

      expect(deps.duckdbRouter).toBeNull();
      expect(deps.opfsManager).toBeNull();
    });

    it('sets analyticsEnabled based on config', async () => {
      const { config: enabledConfig } = createConfig({ enableAnalytics: true });
      const { config: disabledConfig } = createConfig({ enableAnalytics: false });

      const enabledContainer = new DataLayerContainer(enabledConfig);
      const disabledContainer = new DataLayerContainer(disabledConfig);

      const enabledDeps = await enabledContainer.initialize();
      const disabledDeps = await disabledContainer.initialize();

      expect(enabledDeps.analyticsEnabled).toBe(true);
      expect(disabledDeps.analyticsEnabled).toBe(false);
    });
  });

  // 3. Initialize idempotency
  describe('initialize idempotency', () => {
    it('returns the same dependencies on subsequent calls', async () => {
      const { config } = createConfig();
      const container = new DataLayerContainer(config);

      const deps1 = await container.initialize();
      const deps2 = await container.initialize();

      expect(deps1).toBe(deps2);
    });

    it('only initializes database once when called concurrently', async () => {
      const { config, mocks } = createConfig();
      const container = new DataLayerContainer(config);

      const [deps1, deps2] = await Promise.all([container.initialize(), container.initialize()]);

      expect(deps1).toBe(deps2);
      // Factory should only have been called once
      expect(mocks.mockDatabase.startCleanup).toHaveBeenCalledOnce();
    });
  });

  // 4. getDependencies before init throws
  describe('getDependencies before init', () => {
    it('throws when called before initialization', () => {
      const { config } = createConfig();
      const container = new DataLayerContainer(config);

      expect(() => container.getDependencies()).toThrow(
        '[DataLayerContainer] Container not initialized',
      );
    });
  });

  // 5. getDependencies after dispose throws
  describe('getDependencies after dispose', () => {
    it('throws when called after disposal', async () => {
      const { config } = createConfig();
      const container = new DataLayerContainer(config);

      await container.initialize();
      await container.dispose();

      expect(() => container.getDependencies()).toThrow(
        '[DataLayerContainer] Container is disposed',
      );
    });
  });

  // 6. Initialize after dispose throws
  describe('initialize after dispose', () => {
    it('throws when initialize is called after disposal', async () => {
      const { config } = createConfig();
      const container = new DataLayerContainer(config);

      await container.dispose();

      await expect(container.initialize()).rejects.toThrow(
        '[DataLayerContainer] Container is disposed',
      );
    });
  });

  // 7. Dispose - calls cleanup methods
  describe('dispose', () => {
    it('calls cleanup methods during disposal', async () => {
      const { config, mocks } = createConfig();
      const container = new DataLayerContainer(config);

      await container.initialize();
      await container.dispose();

      // Sync coordinator should be disposed
      expect(mocks.mockSyncCoordinator.disposeAsync).toHaveBeenCalledOnce();
      // Database cleanup should be stopped and closed
      expect(mocks.mockDatabase.stopCleanup).toHaveBeenCalledOnce();
      expect(mocks.mockDatabase.close).toHaveBeenCalledOnce();
    });

    it('sets isDisposed to true after disposal', async () => {
      const { config } = createConfig();
      const container = new DataLayerContainer(config);

      await container.initialize();
      await container.dispose();

      expect(container.isDisposed).toBe(true);
    });

    it('sets isInitialized to false after disposal', async () => {
      const { config } = createConfig();
      const container = new DataLayerContainer(config);

      await container.initialize();
      expect(container.isInitialized).toBe(true);

      await container.dispose();
      expect(container.isInitialized).toBe(false);
    });

    it('can dispose without initializing first', async () => {
      const { config } = createConfig();
      const container = new DataLayerContainer(config);

      await expect(container.dispose()).resolves.toBeUndefined();
      expect(container.isDisposed).toBe(true);
    });
  });

  // 8. Dispose idempotency
  describe('dispose idempotency', () => {
    it('is safe to call dispose multiple times', async () => {
      const { config, mocks } = createConfig();
      const container = new DataLayerContainer(config);

      await container.initialize();
      await container.dispose();
      await container.dispose();

      // Cleanup methods should only have been called once
      expect(mocks.mockSyncCoordinator.disposeAsync).toHaveBeenCalledOnce();
      expect(mocks.mockDatabase.stopCleanup).toHaveBeenCalledOnce();
      expect(mocks.mockDatabase.close).toHaveBeenCalledOnce();
    });

    it('is safe to call dispose concurrently', async () => {
      const { config, mocks } = createConfig();
      const container = new DataLayerContainer(config);

      await container.initialize();
      await Promise.all([container.dispose(), container.dispose()]);

      expect(mocks.mockSyncCoordinator.disposeAsync).toHaveBeenCalledOnce();
      expect(mocks.mockDatabase.close).toHaveBeenCalledOnce();
    });
  });

  // 9. isInitialized and isDisposed getters
  describe('isInitialized and isDisposed getters', () => {
    it('reflect lifecycle transitions correctly', async () => {
      const { config } = createConfig();
      const container = new DataLayerContainer(config);

      // Fresh
      expect(container.isInitialized).toBe(false);
      expect(container.isDisposed).toBe(false);

      // After init
      await container.initialize();
      expect(container.isInitialized).toBe(true);
      expect(container.isDisposed).toBe(false);

      // After dispose
      await container.dispose();
      expect(container.isInitialized).toBe(false);
      expect(container.isDisposed).toBe(true);
    });
  });
});

// 10. createDataLayerContainer factory
describe('createDataLayerContainer', () => {
  it('returns a DataLayerContainer instance', () => {
    const { config } = createConfig();
    const container = createDataLayerContainer(config);

    expect(container).toBeInstanceOf(DataLayerContainer);
  });

  it('creates a fully functional container', async () => {
    const { config } = createConfig();
    const container = createDataLayerContainer(config);

    const deps = await container.initialize();
    expect(deps).toBeDefined();
    expect(deps.database).toBeDefined();
    expect(deps.syncCoordinator).toBeDefined();

    await container.dispose();
    expect(container.isDisposed).toBe(true);
  });
});
