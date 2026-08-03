/**
 * Data source contracts for analytics file synchronization.
 *
 * Shared between data-layer and query-engine to avoid duplicated shape logic.
 *
 * @module datasource/types
 */

export interface DataSourceFileInfo {
  readonly url: string;
  readonly filename: string;
  readonly size: number;
  readonly rowCount?: number;
  readonly hash?: string;
  readonly partition?: Readonly<Record<string, string>>;
}

export interface DataSourceTableInfo {
  readonly name: string;
  readonly files: ReadonlyArray<DataSourceFileInfo>;
  readonly lastIngestedAt: number;
  readonly totalRows: number;
  readonly totalSize: number;
  readonly schema: Readonly<Record<string, string>>;
  readonly expiresAt?: number;
  readonly partitionColumns?: ReadonlyArray<string>;
  readonly compression?: string;
}

export interface DataSourceMetadata {
  readonly totalSize: number;
  readonly estimatedDownloadTimeMs?: number;
  readonly serverTimestamp?: number;
  readonly notFoundTables?: ReadonlyArray<string>;
  readonly errorTables?: ReadonlyArray<{
    readonly name: string;
    readonly error: string;
  }>;
}

export interface DataSourceResponse {
  readonly tables: ReadonlyArray<DataSourceTableInfo>;
  readonly metadata?: DataSourceMetadata;
}

export interface DataSourceRequest {
  readonly tables: ReadonlyArray<string>;
  readonly includeSchema?: boolean;
  readonly includePartitions?: boolean;
  readonly partitionFilter?: Readonly<Record<string, string>>;
  readonly maxAge?: number;
}

export const isDataSourceFileInfo = (value: unknown): value is DataSourceFileInfo => {
  if (typeof value !== 'object' || value === null) {
    return false;
  }

  const obj = value as Record<string, unknown>;
  return (
    typeof obj['url'] === 'string' &&
    typeof obj['filename'] === 'string' &&
    typeof obj['size'] === 'number'
  );
};

export const isDataSourceTableInfo = (value: unknown): value is DataSourceTableInfo => {
  if (typeof value !== 'object' || value === null) {
    return false;
  }

  const obj = value as Record<string, unknown>;
  return (
    typeof obj['name'] === 'string' &&
    Array.isArray(obj['files']) &&
    typeof obj['lastIngestedAt'] === 'number' &&
    typeof obj['totalRows'] === 'number' &&
    typeof obj['totalSize'] === 'number' &&
    typeof obj['schema'] === 'object'
  );
};

export const isDataSourceResponse = (value: unknown): value is DataSourceResponse => {
  if (typeof value !== 'object' || value === null) {
    return false;
  }

  const obj = value as Record<string, unknown>;
  return Array.isArray(obj['tables']) && obj['tables'].every(isDataSourceTableInfo);
};

export const calculateTableSize = (table: DataSourceTableInfo): number =>
  table.files.reduce((sum, file) => sum + file.size, 0);

export const calculateTotalRows = (tables: ReadonlyArray<DataSourceTableInfo>): number =>
  tables.reduce((sum, table) => sum + table.totalRows, 0);

export const calculateTotalSize = (tables: ReadonlyArray<DataSourceTableInfo>): number =>
  tables.reduce((sum, table) => sum + table.totalSize, 0);

export const getTablesNeedingUpdate = (
  response: DataSourceResponse,
  clientLoadTimes: Readonly<Record<string, number>>,
): ReadonlyArray<DataSourceTableInfo> =>
  response.tables.filter((table) => {
    const clientLoadedAt = clientLoadTimes[table.name];
    if (!clientLoadedAt) {
      return true;
    }
    return table.lastIngestedAt > clientLoadedAt;
  });

export const hasExpiredUrls = (response: DataSourceResponse): boolean => {
  const now = Date.now();
  return response.tables.some((table) => {
    if (table.expiresAt && table.expiresAt < now) {
      return true;
    }
    return false;
  });
};
