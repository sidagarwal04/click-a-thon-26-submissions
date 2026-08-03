import {
  CONFLICT_STRATEGY,
  DATA_FRESHNESS,
  type UnifiedTableConfig,
} from '@open-zentra/foundation-data-model';
import { TIME_MS } from '@open-zentra/foundation-utils';

import { createTableRegistry, TableRegistry } from './table-registry';

// =============================================================================
// MOCK DATA
// =============================================================================

const mockTable: UnifiedTableConfig = { name: 'users' };

const mockTableWithCache: UnifiedTableConfig = {
  name: 'posts',
  staleTime: 10_000,
  gcTime: 120_000,
};

const mockTableWithConflict: UnifiedTableConfig = {
  name: 'comments',
  conflictStrategy: CONFLICT_STRATEGY.SERVER_WINS,
  mergeConfig: {
    serverFields: ['updatedAt', 'version'],
    clientFields: ['draft'],
    deepMergeFields: ['metadata'],
  },
};

const mockTableWithAnalytics: UnifiedTableConfig = {
  name: 'events',
  analytics: {
    enabled: true,
    freshness: DATA_FRESHNESS.EVENTUAL,
    staleTime: 60_000,
  },
};

const mockTableAnalyticsDisabled: UnifiedTableConfig = {
  name: 'settings',
  analytics: {
    enabled: false,
  },
};

const mockTableAnalyticsNoFreshness: UnifiedTableConfig = {
  name: 'logs',
  analytics: {
    enabled: true,
  },
};

const allMockTables: ReadonlyArray<UnifiedTableConfig> = [
  mockTable,
  mockTableWithCache,
  mockTableWithConflict,
  mockTableWithAnalytics,
  mockTableAnalyticsDisabled,
  mockTableAnalyticsNoFreshness,
];

// =============================================================================
// TESTS
// =============================================================================

describe('TableRegistry', () => {
  // ─── CONSTRUCTION ──────────────────────────────────────────────────────────

  describe('construction', () => {
    it('should create an empty registry with no arguments', () => {
      const registry = new TableRegistry();

      expect(registry.getAllTables()).toEqual([]);
      expect(registry.getTableNames()).toEqual([]);
    });

    it('should create an empty registry with an empty array', () => {
      const registry = new TableRegistry([]);

      expect(registry.getAllTables()).toHaveLength(0);
    });

    it('should create a registry with provided tables', () => {
      const registry = new TableRegistry(allMockTables);

      expect(registry.getAllTables()).toHaveLength(allMockTables.length);
      expect(registry.getTableNames()).toEqual(
        expect.arrayContaining(['users', 'posts', 'comments', 'events', 'settings', 'logs']),
      );
    });

    it('should handle duplicate table names at construction (last config wins, no crash)', () => {
      const firstConfig: UnifiedTableConfig = { name: 'users', staleTime: 1000 };
      const secondConfig: UnifiedTableConfig = { name: 'users', staleTime: 9999 };

      const registry = new TableRegistry([firstConfig, secondConfig]);

      // Should not crash, and last config wins
      expect(registry.hasTable('users')).toBe(true);
      expect(registry.getTable('users')).toEqual(secondConfig);
      expect(registry.getTable('users')?.staleTime).toBe(9999);
      // Only one entry for the duplicate name
      expect(registry.getAllTables()).toHaveLength(1);
    });
  });

  // ─── BASIC ACCESSORS ───────────────────────────────────────────────────────

  describe('basic accessors', () => {
    let registry: TableRegistry;

    beforeEach(() => {
      registry = new TableRegistry(allMockTables);
    });

    describe('getTable', () => {
      it('should return the config for a registered table', () => {
        expect(registry.getTable('users')).toEqual(mockTable);
      });

      it('should return undefined for an unregistered table', () => {
        expect(registry.getTable('nonexistent')).toBeUndefined();
      });
    });

    describe('getTableOrThrow', () => {
      it('should return the config for a registered table', () => {
        expect(registry.getTableOrThrow('users')).toEqual(mockTable);
      });

      it('should throw for an unregistered table', () => {
        expect(() => registry.getTableOrThrow('nonexistent')).toThrow(
          "[TableRegistry] Table 'nonexistent' not registered",
        );
      });
    });

    describe('hasTable', () => {
      it('should return true for a registered table', () => {
        expect(registry.hasTable('users')).toBe(true);
        expect(registry.hasTable('events')).toBe(true);
      });

      it('should return false for an unregistered table', () => {
        expect(registry.hasTable('nonexistent')).toBe(false);
      });
    });

    describe('getAllTables', () => {
      it('should return all registered table configs', () => {
        const tables = registry.getAllTables();
        expect(tables).toHaveLength(allMockTables.length);
        // Spread because arrayContaining takes a mutable array; allMockTables is readonly.
        expect(tables).toEqual(expect.arrayContaining([...allMockTables]));
      });

      it('should return an empty array for an empty registry', () => {
        const emptyRegistry = new TableRegistry();
        expect(emptyRegistry.getAllTables()).toEqual([]);
      });
    });

    describe('getTableNames', () => {
      it('should return all registered table names', () => {
        const names = registry.getTableNames();
        expect(names).toHaveLength(allMockTables.length);
        expect(names).toEqual(
          expect.arrayContaining(['users', 'posts', 'comments', 'events', 'settings', 'logs']),
        );
      });

      it('should return an empty array for an empty registry', () => {
        const emptyRegistry = new TableRegistry();
        expect(emptyRegistry.getTableNames()).toEqual([]);
      });
    });
  });

  // ─── REGISTER / UNREGISTER ─────────────────────────────────────────────────

  describe('registerTable', () => {
    it('should register a new table', () => {
      const registry = new TableRegistry();

      registry.registerTable({ name: 'newTable' });

      expect(registry.hasTable('newTable')).toBe(true);
      expect(registry.getTable('newTable')).toEqual({ name: 'newTable' });
    });

    it('should overwrite an existing table (with warning, no crash)', () => {
      const registry = new TableRegistry([mockTable]);
      const updatedConfig: UnifiedTableConfig = { name: 'users', staleTime: 5000 };

      registry.registerTable(updatedConfig);

      expect(registry.getTable('users')).toEqual(updatedConfig);
      expect(registry.getTable('users')?.staleTime).toBe(5000);
    });

    it('should suppress warning when using force option', () => {
      const registry = new TableRegistry([mockTable]);
      const updatedConfig: UnifiedTableConfig = { name: 'users', staleTime: 5000 };

      // Should not warn — we can't easily assert on logger, but ensure no crash
      registry.registerTable(updatedConfig, { force: true });

      expect(registry.getTable('users')).toEqual(updatedConfig);
    });

    it('should not warn when registering a genuinely new table', () => {
      const registry = new TableRegistry([mockTable]);

      registry.registerTable({ name: 'brand_new' });

      expect(registry.hasTable('brand_new')).toBe(true);
      expect(registry.getAllTables()).toHaveLength(2);
    });
  });

  describe('unregisterTable', () => {
    it('should remove an existing table and return true', () => {
      const registry = new TableRegistry([mockTable, mockTableWithCache]);

      const result = registry.unregisterTable('users');

      expect(result).toBe(true);
      expect(registry.hasTable('users')).toBe(false);
      expect(registry.getAllTables()).toHaveLength(1);
    });

    it('should return false when table does not exist', () => {
      const registry = new TableRegistry([mockTable]);

      const result = registry.unregisterTable('nonexistent');

      expect(result).toBe(false);
    });

    it('should not affect other tables when unregistering', () => {
      const registry = new TableRegistry([mockTable, mockTableWithCache]);

      registry.unregisterTable('users');

      expect(registry.hasTable('posts')).toBe(true);
      expect(registry.getTable('posts')).toEqual(mockTableWithCache);
    });
  });

  // ─── API DESCRIPTOR ACCESSORS ─────────────────────────────────────────────

  describe('api descriptor accessors', () => {
    it('should return undefined for getApiDescriptor when table has no api config', () => {
      const registry = new TableRegistry([mockTable]);

      expect(registry.getApiDescriptor('users', 'list')).toBeUndefined();
      expect(registry.getApiDescriptor('users', 'get')).toBeUndefined();
      expect(registry.getApiDescriptor('users', 'create')).toBeUndefined();
      expect(registry.getApiDescriptor('users', 'update')).toBeUndefined();
      expect(registry.getApiDescriptor('users', 'delete')).toBeUndefined();
    });

    it('should return undefined for getApiDescriptor when table does not exist', () => {
      const registry = new TableRegistry();

      expect(registry.getApiDescriptor('nonexistent', 'list')).toBeUndefined();
    });

    it('should return empty mutation descriptors when table has no api config', () => {
      const registry = new TableRegistry([mockTable]);

      const refs = registry.getMutationDescriptors('users');

      expect(refs.create).toBeUndefined();
      expect(refs.update).toBeUndefined();
      expect(refs.delete).toBeUndefined();
    });

    it('should return empty mutation descriptors when table does not exist', () => {
      const registry = new TableRegistry();

      const refs = registry.getMutationDescriptors('nonexistent');

      expect(refs.create).toBeUndefined();
      expect(refs.update).toBeUndefined();
      expect(refs.delete).toBeUndefined();
    });

    it('should return false for hasApiDescriptor when table has no api config', () => {
      const registry = new TableRegistry([mockTable]);

      expect(registry.hasApiDescriptor('users', 'list')).toBe(false);
      expect(registry.hasApiDescriptor('users', 'create')).toBe(false);
    });

    it('should return false for hasApiDescriptor when table does not exist', () => {
      const registry = new TableRegistry();

      expect(registry.hasApiDescriptor('nonexistent', 'list')).toBe(false);
    });
  });

  // ─── CACHE ACCESSORS ──────────────────────────────────────────────────────

  describe('cache accessors', () => {
    describe('getStaleTime', () => {
      it('should return the global default when table has no override', () => {
        const registry = new TableRegistry([mockTable]);

        // Default: TIME_MS.MINUTE * 5 = 300_000
        expect(registry.getStaleTime('users')).toBe(TIME_MS.MINUTE * 5);
      });

      it('should return per-table staleTime override', () => {
        const registry = new TableRegistry([mockTableWithCache]);

        expect(registry.getStaleTime('posts')).toBe(10_000);
      });

      it('should return custom default when provided in constructor', () => {
        const registry = new TableRegistry([mockTable], { staleTime: 42_000 });

        expect(registry.getStaleTime('users')).toBe(42_000);
      });

      it('should prefer per-table override over custom default', () => {
        const registry = new TableRegistry([mockTableWithCache], { staleTime: 42_000 });

        expect(registry.getStaleTime('posts')).toBe(10_000);
      });

      it('should return default staleTime for non-existent table', () => {
        const registry = new TableRegistry();

        expect(registry.getStaleTime('nonexistent')).toBe(TIME_MS.MINUTE * 5);
      });
    });

    describe('getGcTime', () => {
      it('should return the global default when table has no override', () => {
        const registry = new TableRegistry([mockTable]);

        // Default: TIME_MS.DAY = 86_400_000
        expect(registry.getGcTime('users')).toBe(TIME_MS.DAY);
      });

      it('should return per-table gcTime override', () => {
        const registry = new TableRegistry([mockTableWithCache]);

        expect(registry.getGcTime('posts')).toBe(120_000);
      });

      it('should return custom default when provided in constructor', () => {
        const registry = new TableRegistry([mockTable], { gcTime: 500_000 });

        expect(registry.getGcTime('users')).toBe(500_000);
      });

      it('should prefer per-table override over custom default', () => {
        const registry = new TableRegistry([mockTableWithCache], { gcTime: 500_000 });

        expect(registry.getGcTime('posts')).toBe(120_000);
      });

      it('should return default gcTime for non-existent table', () => {
        const registry = new TableRegistry();

        expect(registry.getGcTime('nonexistent')).toBe(TIME_MS.DAY);
      });
    });
  });

  // ─── CONFLICT ACCESSORS ────────────────────────────────────────────────────

  describe('conflict accessors', () => {
    describe('getConflictStrategy', () => {
      it('should return the global default when table has no override', () => {
        const registry = new TableRegistry([mockTable]);

        expect(registry.getConflictStrategy('users')).toBe(CONFLICT_STRATEGY.LAST_WRITE_WINS);
      });

      it('should return per-table conflict strategy override', () => {
        const registry = new TableRegistry([mockTableWithConflict]);

        expect(registry.getConflictStrategy('comments')).toBe(CONFLICT_STRATEGY.SERVER_WINS);
      });

      it('should return custom default when provided in constructor', () => {
        const registry = new TableRegistry([mockTable], {
          conflictStrategy: CONFLICT_STRATEGY.CLIENT_WINS,
        });

        expect(registry.getConflictStrategy('users')).toBe(CONFLICT_STRATEGY.CLIENT_WINS);
      });

      it('should prefer per-table override over custom default', () => {
        const registry = new TableRegistry([mockTableWithConflict], {
          conflictStrategy: CONFLICT_STRATEGY.CLIENT_WINS,
        });

        expect(registry.getConflictStrategy('comments')).toBe(CONFLICT_STRATEGY.SERVER_WINS);
      });

      it('should return default for non-existent table', () => {
        const registry = new TableRegistry();

        expect(registry.getConflictStrategy('nonexistent')).toBe(CONFLICT_STRATEGY.LAST_WRITE_WINS);
      });
    });

    describe('getMergeConfig', () => {
      it('should return merge config when set', () => {
        const registry = new TableRegistry([mockTableWithConflict]);

        const config = registry.getMergeConfig('comments');

        expect(config).toBeDefined();
        expect(config?.serverFields).toEqual(['updatedAt', 'version']);
        expect(config?.clientFields).toEqual(['draft']);
        expect(config?.deepMergeFields).toEqual(['metadata']);
      });

      it('should return undefined when merge config is not set', () => {
        const registry = new TableRegistry([mockTable]);

        expect(registry.getMergeConfig('users')).toBeUndefined();
      });

      it('should return undefined for non-existent table', () => {
        const registry = new TableRegistry();

        expect(registry.getMergeConfig('nonexistent')).toBeUndefined();
      });
    });

    describe('getTableStrategies', () => {
      it('should return strategies only for tables with explicit conflictStrategy', () => {
        const registry = new TableRegistry(allMockTables);

        const strategies = registry.getTableStrategies();

        // Only mockTableWithConflict has an explicit conflictStrategy
        expect(strategies).toEqual({
          comments: CONFLICT_STRATEGY.SERVER_WINS,
        });
      });

      it('should return empty object when no tables have explicit strategies', () => {
        const registry = new TableRegistry([mockTable, mockTableWithCache]);

        expect(registry.getTableStrategies()).toEqual({});
      });

      it('should return empty object for empty registry', () => {
        const registry = new TableRegistry();

        expect(registry.getTableStrategies()).toEqual({});
      });
    });

    describe('getTableMergeConfigs', () => {
      it('should return merge configs only for tables with explicit mergeConfig', () => {
        const registry = new TableRegistry(allMockTables);

        const configs = registry.getTableMergeConfigs();

        expect(Object.keys(configs)).toEqual(['comments']);
        expect(configs['comments']).toEqual(mockTableWithConflict.mergeConfig);
      });

      it('should return empty object when no tables have merge configs', () => {
        const registry = new TableRegistry([mockTable, mockTableWithCache]);

        expect(registry.getTableMergeConfigs()).toEqual({});
      });

      it('should return empty object for empty registry', () => {
        const registry = new TableRegistry();

        expect(registry.getTableMergeConfigs()).toEqual({});
      });
    });
  });

  // ─── ANALYTICS ACCESSORS ───────────────────────────────────────────────────

  describe('analytics accessors', () => {
    let registry: TableRegistry;

    beforeEach(() => {
      registry = new TableRegistry(allMockTables);
    });

    describe('isAnalyticsEnabled', () => {
      it('should return true when analytics is explicitly enabled', () => {
        expect(registry.isAnalyticsEnabled('events')).toBe(true);
        expect(registry.isAnalyticsEnabled('logs')).toBe(true);
      });

      it('should return false when analytics is explicitly disabled', () => {
        expect(registry.isAnalyticsEnabled('settings')).toBe(false);
      });

      it('should return false when analytics is not configured', () => {
        expect(registry.isAnalyticsEnabled('users')).toBe(false);
      });

      it('should return false for non-existent table', () => {
        expect(registry.isAnalyticsEnabled('nonexistent')).toBe(false);
      });
    });

    describe('getAnalyticsFreshness', () => {
      it('should return configured freshness level', () => {
        expect(registry.getAnalyticsFreshness('events')).toBe(DATA_FRESHNESS.EVENTUAL);
      });

      it('should return NEAR_REALTIME as default when freshness is not configured', () => {
        expect(registry.getAnalyticsFreshness('logs')).toBe(DATA_FRESHNESS.NEAR_REALTIME);
      });

      it('should return NEAR_REALTIME for tables without analytics config', () => {
        expect(registry.getAnalyticsFreshness('users')).toBe(DATA_FRESHNESS.NEAR_REALTIME);
      });

      it('should return NEAR_REALTIME for non-existent table', () => {
        expect(registry.getAnalyticsFreshness('nonexistent')).toBe(DATA_FRESHNESS.NEAR_REALTIME);
      });
    });

    describe('getAnalyticsStaleTime', () => {
      it('should return configured analytics stale time', () => {
        expect(registry.getAnalyticsStaleTime('events')).toBe(60_000);
      });

      it('should return default stale time when analytics staleTime is not configured', () => {
        // Defaults to this.defaults.staleTime = TIME_MS.MINUTE * 5 = 300_000
        expect(registry.getAnalyticsStaleTime('logs')).toBe(TIME_MS.MINUTE * 5);
      });

      it('should return default stale time for tables without analytics config', () => {
        expect(registry.getAnalyticsStaleTime('users')).toBe(TIME_MS.MINUTE * 5);
      });

      it('should return default stale time for non-existent table', () => {
        expect(registry.getAnalyticsStaleTime('nonexistent')).toBe(TIME_MS.MINUTE * 5);
      });

      it('should use custom default stale time from constructor', () => {
        const customRegistry = new TableRegistry([mockTableAnalyticsNoFreshness], {
          staleTime: 99_000,
        });

        // logs has analytics.enabled but no analytics.staleTime → falls back to defaults.staleTime
        expect(customRegistry.getAnalyticsStaleTime('logs')).toBe(99_000);
      });
    });

    describe('getAnalyticsTables', () => {
      it('should return only tables with analytics enabled', () => {
        const analyticsTables = registry.getAnalyticsTables();

        expect(analyticsTables).toHaveLength(2);
        expect(analyticsTables).toContain('events');
        expect(analyticsTables).toContain('logs');
      });

      it('should not include tables with analytics disabled', () => {
        const analyticsTables = registry.getAnalyticsTables();

        expect(analyticsTables).not.toContain('settings');
      });

      it('should not include tables without analytics config', () => {
        const analyticsTables = registry.getAnalyticsTables();

        expect(analyticsTables).not.toContain('users');
        expect(analyticsTables).not.toContain('posts');
        expect(analyticsTables).not.toContain('comments');
      });

      it('should return empty array for empty registry', () => {
        const emptyRegistry = new TableRegistry();

        expect(emptyRegistry.getAnalyticsTables()).toEqual([]);
      });

      it('should return empty array when no tables have analytics enabled', () => {
        const registry = new TableRegistry([mockTable, mockTableWithCache]);

        expect(registry.getAnalyticsTables()).toEqual([]);
      });
    });
  });

  // ─── DEFAULTS ──────────────────────────────────────────────────────────────

  describe('constructor defaults', () => {
    it('should apply default staleTime of 5 minutes', () => {
      const registry = new TableRegistry([mockTable]);

      expect(registry.getStaleTime('users')).toBe(TIME_MS.MINUTE * 5);
    });

    it('should apply default gcTime of 1 day', () => {
      const registry = new TableRegistry([mockTable]);

      expect(registry.getGcTime('users')).toBe(TIME_MS.DAY);
    });

    it('should apply default conflictStrategy of LAST_WRITE_WINS', () => {
      const registry = new TableRegistry([mockTable]);

      expect(registry.getConflictStrategy('users')).toBe(CONFLICT_STRATEGY.LAST_WRITE_WINS);
    });

    it('should allow overriding all defaults', () => {
      const registry = new TableRegistry([mockTable], {
        staleTime: 1000,
        gcTime: 2000,
        conflictStrategy: CONFLICT_STRATEGY.MERGE,
      });

      expect(registry.getStaleTime('users')).toBe(1000);
      expect(registry.getGcTime('users')).toBe(2000);
      expect(registry.getConflictStrategy('users')).toBe(CONFLICT_STRATEGY.MERGE);
    });
  });
});

// =============================================================================
// FACTORY
// =============================================================================

describe('createTableRegistry', () => {
  it('should create a TableRegistry instance', () => {
    const registry = createTableRegistry();

    expect(registry).toBeInstanceOf(TableRegistry);
  });

  it('should create a registry with tables', () => {
    const registry = createTableRegistry([mockTable, mockTableWithAnalytics]);

    expect(registry.hasTable('users')).toBe(true);
    expect(registry.hasTable('events')).toBe(true);
    expect(registry.getAllTables()).toHaveLength(2);
  });

  it('should create a registry with custom defaults', () => {
    const registry = createTableRegistry([mockTable], {
      staleTime: 7000,
      gcTime: 14_000,
      conflictStrategy: CONFLICT_STRATEGY.SERVER_WINS,
    });

    expect(registry.getStaleTime('users')).toBe(7000);
    expect(registry.getGcTime('users')).toBe(14_000);
    expect(registry.getConflictStrategy('users')).toBe(CONFLICT_STRATEGY.SERVER_WINS);
  });

  it('should create an empty registry when called with no arguments', () => {
    const registry = createTableRegistry();

    expect(registry.getAllTables()).toEqual([]);
    expect(registry.getTableNames()).toEqual([]);
  });

  it('should accept debug flag without affecting behavior', () => {
    const registry = createTableRegistry([mockTable], { debug: true });

    expect(registry).toBeInstanceOf(TableRegistry);
    expect(registry.hasTable('users')).toBe(true);
  });
});
