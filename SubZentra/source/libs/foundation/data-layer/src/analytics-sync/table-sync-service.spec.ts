/**
 * Tests for TableSyncService
 *
 * @module analytics-sync/table-sync-service.spec
 */

import type {
  ApiQueryDescriptor,
  DataSourceFileInfo,
  DataSourceResponse,
  DataSourceTableInfo,
} from '@open-zentra/foundation-data-model';

import {
  TableSyncService,
  type LocalTableMetadata,
  type TableSyncDatabaseOperations,
  type TableSyncServiceConfig,
} from './table-sync-service';

// ---------------------------------------------------------------------------
// Helpers & Mocks
// ---------------------------------------------------------------------------

const MOCK_DATASOURCE_API = {
  path: '/datasource',
} as ApiQueryDescriptor<{ tables: string[] }, DataSourceResponse>;

function createMockDatabase(): TableSyncDatabaseOperations {
  return {
    get: vi
      .fn<(name: string) => Promise<LocalTableMetadata | undefined>>()
      .mockResolvedValue(undefined),
    set: vi.fn<(entry: LocalTableMetadata) => Promise<void>>().mockResolvedValue(undefined),
    getMany: vi
      .fn<(names: string[]) => Promise<Map<string, LocalTableMetadata | undefined>>>()
      .mockResolvedValue(new Map()),
  };
}

function makeFileInfo(overrides: Partial<DataSourceFileInfo> = {}): DataSourceFileInfo {
  return {
    url: 'https://example.com/file.parquet',
    filename: 'file.parquet',
    size: 1024,
    rowCount: 100,
    hash: 'abc123',
    ...overrides,
  };
}

function makeTableInfo(overrides: Partial<DataSourceTableInfo> = {}): DataSourceTableInfo {
  return {
    name: 'events',
    files: [makeFileInfo()],
    lastIngestedAt: 2000,
    totalRows: 100,
    totalSize: 1024,
    schema: { id: 'VARCHAR', ts: 'TIMESTAMP' },
    ...overrides,
  };
}

function makeLocalMetadata(overrides: Partial<LocalTableMetadata> = {}): LocalTableMetadata {
  return {
    name: 'events',
    lastIngestedAt: 1000,
    loadedAt: 1500,
    fileHashes: { 'file.parquet': 'abc123' },
    totalSize: 1024,
    totalRows: 100,
    ...overrides,
  };
}

function createService(overrides: Partial<TableSyncServiceConfig> = {}): {
  service: TableSyncService;
  database: TableSyncDatabaseOperations;
} {
  const database = createMockDatabase();
  const service = new TableSyncService({
    // The service only calls `request`; via unknown because a two-property
    // stand-in does not overlap the full AxiosInstance surface.
    axiosInstance: { request: vi.fn(), defaults: {} } as unknown as TableSyncServiceConfig['axiosInstance'],
    datasourceEndpoint: MOCK_DATASOURCE_API,
    database,
    debug: false,
    ...overrides,
  });
  return { service, database };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('TableSyncService', () => {
  // ── isConfigured ────────────────────────────────────────────────────────

  describe('isConfigured', () => {
    it('returns true when datasourceEndpoint is set', () => {
      const { service } = createService();
      expect(service.isConfigured()).toBe(true);
    });

    it('returns false when datasourceEndpoint is null', () => {
      const { service } = createService({ datasourceEndpoint: null });
      expect(service.isConfigured()).toBe(false);
    });
  });

  // ── needsUpdate ─────────────────────────────────────────────────────────

  describe('needsUpdate', () => {
    it('returns true when local is undefined (never synced)', () => {
      const { service } = createService();
      const remote = makeTableInfo();

      expect(service.needsUpdate(remote, undefined)).toBe(true);
    });

    it('returns true when remote.lastIngestedAt > local.loadedAt', () => {
      const { service } = createService();
      const remote = makeTableInfo({ lastIngestedAt: 3000 });
      const local = makeLocalMetadata({ loadedAt: 1500 });

      expect(service.needsUpdate(remote, local)).toBe(true);
    });

    it('returns false when remote.lastIngestedAt <= local.loadedAt', () => {
      const { service } = createService();
      const remote = makeTableInfo({ lastIngestedAt: 1000 });
      const local = makeLocalMetadata({ loadedAt: 1500 });

      expect(service.needsUpdate(remote, local)).toBe(false);
    });
  });

  // ── getFilesToDownload ──────────────────────────────────────────────────

  describe('getFilesToDownload', () => {
    it('returns all files when local is undefined', () => {
      const { service } = createService();
      const files = [
        makeFileInfo({ filename: 'a.parquet', hash: 'h1' }),
        makeFileInfo({ filename: 'b.parquet', hash: 'h2' }),
      ];
      const remote = makeTableInfo({ files });

      const result = service.getFilesToDownload(remote, undefined);

      expect(result).toEqual(files);
    });

    it('returns only files with changed hashes', () => {
      const { service } = createService();
      const files = [
        makeFileInfo({ filename: 'a.parquet', hash: 'h1' }),
        makeFileInfo({ filename: 'b.parquet', hash: 'h2-new' }),
      ];
      const remote = makeTableInfo({ files });
      const local = makeLocalMetadata({
        fileHashes: { 'a.parquet': 'h1', 'b.parquet': 'h2-old' },
      });

      const result = service.getFilesToDownload(remote, local);

      expect(result).toEqual([files[1]]);
    });

    it('returns empty array when all hashes match', () => {
      const { service } = createService();
      const files = [
        makeFileInfo({ filename: 'a.parquet', hash: 'h1' }),
        makeFileInfo({ filename: 'b.parquet', hash: 'h2' }),
      ];
      const remote = makeTableInfo({ files });
      const local = makeLocalMetadata({
        fileHashes: { 'a.parquet': 'h1', 'b.parquet': 'h2' },
      });

      const result = service.getFilesToDownload(remote, local);

      expect(result).toEqual([]);
    });
  });

  // ── analyzeUpdates ─────────────────────────────────────────────────────

  describe('analyzeUpdates', () => {
    it('returns plans for tables needing updates', () => {
      const { service } = createService();
      const tableA = makeTableInfo({ name: 'table_a', lastIngestedAt: 5000 });
      const tableB = makeTableInfo({ name: 'table_b', lastIngestedAt: 5000 });
      const response: DataSourceResponse = { tables: [tableA, tableB] };

      const localMetadata = new Map<string, LocalTableMetadata | undefined>([
        ['table_a', undefined],
        ['table_b', undefined],
      ]);

      const plans = service.analyzeUpdates(response, localMetadata);

      expect(plans).toHaveLength(2);
      expect(plans[0].tableName).toBe('table_a');
      expect(plans[0].needsUpdate).toBe(true);
      expect(plans[0].filesToDownload.length).toBeGreaterThan(0);
      expect(plans[1].tableName).toBe('table_b');
      expect(plans[1].needsUpdate).toBe(true);
    });

    it('filters out tables that do not need updates', () => {
      const { service } = createService();
      const staleTable = makeTableInfo({ name: 'stale', lastIngestedAt: 5000 });
      const freshTable = makeTableInfo({ name: 'fresh', lastIngestedAt: 1000 });
      const response: DataSourceResponse = { tables: [staleTable, freshTable] };

      const localMetadata = new Map<string, LocalTableMetadata | undefined>([
        ['stale', undefined],
        ['fresh', makeLocalMetadata({ name: 'fresh', loadedAt: 2000 })],
      ]);

      const plans = service.analyzeUpdates(response, localMetadata);

      expect(plans).toHaveLength(1);
      expect(plans[0].tableName).toBe('stale');
    });
  });

  // ── createLocalMetadata ────────────────────────────────────────────────

  describe('createLocalMetadata', () => {
    it('creates metadata with correct fields', () => {
      const { service } = createService();
      const info = makeTableInfo({
        name: 'orders',
        lastIngestedAt: 4000,
        totalSize: 2048,
        totalRows: 500,
        files: [
          makeFileInfo({ filename: 'part1.parquet', hash: 'hash1' }),
          makeFileInfo({ filename: 'part2.parquet', hash: 'hash2' }),
        ],
      });

      const nowBefore = Date.now();
      const metadata = service.createLocalMetadata('orders', info);
      const nowAfter = Date.now();

      expect(metadata.name).toBe('orders');
      expect(metadata.lastIngestedAt).toBe(4000);
      expect(metadata.loadedAt).toBeGreaterThanOrEqual(nowBefore);
      expect(metadata.loadedAt).toBeLessThanOrEqual(nowAfter);
      expect(metadata.fileHashes).toEqual({
        'part1.parquet': 'hash1',
        'part2.parquet': 'hash2',
      });
      expect(metadata.totalSize).toBe(2048);
      expect(metadata.totalRows).toBe(500);
    });
  });

  // ── updateLocalMetadata ────────────────────────────────────────────────

  describe('updateLocalMetadata', () => {
    it('calls database.set with created metadata', async () => {
      const { service, database } = createService();
      const info = makeTableInfo({
        name: 'users',
        lastIngestedAt: 6000,
        totalSize: 4096,
        totalRows: 200,
        files: [makeFileInfo({ filename: 'users.parquet', hash: 'uhash' })],
      });

      await service.updateLocalMetadata('users', info);

      expect(database.set).toHaveBeenCalledTimes(1);

      const savedMetadata = (database.set as ReturnType<typeof vi.fn>).mock
        .calls[0][0] as LocalTableMetadata;
      expect(savedMetadata.name).toBe('users');
      expect(savedMetadata.lastIngestedAt).toBe(6000);
      expect(savedMetadata.totalSize).toBe(4096);
      expect(savedMetadata.totalRows).toBe(200);
      expect(savedMetadata.fileHashes).toEqual({ 'users.parquet': 'uhash' });
    });
  });
});
