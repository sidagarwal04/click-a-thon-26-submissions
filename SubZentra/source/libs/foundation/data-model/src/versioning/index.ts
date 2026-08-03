/**
 * Schema versioning and migrations
 * @module versioning
 */

/**
 * Current schema version
 * Increment when making breaking changes to schemas
 */
export const SCHEMA_VERSION = 1;

/**
 * Migration function type
 */
export type MigrationFn<TFrom = unknown, TTo = unknown> = (data: TFrom) => TTo;

/**
 * Migration definition
 */
export interface Migration {
  /** Version this migration upgrades FROM */
  fromVersion: number;
  /** Version this migration upgrades TO */
  toVersion: number;
  /** Tables affected by this migration */
  tables: string[];
  /** Description of the migration */
  description: string;
  /** Migration function */
  migrate: MigrationFn;
  /** Rollback function (optional) */
  rollback?: MigrationFn;
}

/**
 * Registry of all migrations
 */
export const migrations: Migration[] = [
  // Future migrations will be added here
  // Example:
  // {
  //   fromVersion: 1,
  //   toVersion: 2,
  //   tables: ['users'],
  //   description: 'Add avatarUrl field to users',
  //   migrate: (user: UserV1) => ({
  //     ...user,
  //     avatarUrl: null,
  //   }),
  //   rollback: (user: UserV2) => {
  //     const { avatarUrl, ...rest } = user;
  //     return rest;
  //   },
  // },
];

/**
 * Get migrations needed to upgrade from one version to another
 */
export function getMigrationPath(
  fromVersion: number,
  toVersion: number = SCHEMA_VERSION,
): Migration[] {
  if (fromVersion >= toVersion) {
    return [];
  }

  return migrations
    .filter((m) => m.fromVersion >= fromVersion && m.toVersion <= toVersion)
    .sort((a, b) => a.fromVersion - b.fromVersion);
}

/**
 * Apply migrations to a data object
 */
export function applyMigrations<T>(
  data: unknown,
  fromVersion: number,
  toVersion: number = SCHEMA_VERSION,
): T {
  const path = getMigrationPath(fromVersion, toVersion);

  return path.reduce((current, migration) => {
    return migration.migrate(current);
  }, data) as T;
}

/**
 * Check if data needs migration
 */
export function needsMigration(dataVersion: number): boolean {
  return dataVersion < SCHEMA_VERSION;
}

/**
 * Versioned data wrapper
 */
export interface VersionedData<T> {
  version: number;
  data: T;
  migratedAt?: string;
}

/**
 * Wrap data with version info
 */
export function wrapWithVersion<T>(data: T, version: number = SCHEMA_VERSION): VersionedData<T> {
  return {
    version,
    data,
  };
}

/**
 * Unwrap and migrate versioned data if needed
 */
export function unwrapAndMigrate<T>(versioned: VersionedData<unknown>): T {
  if (needsMigration(versioned.version)) {
    return applyMigrations<T>(versioned.data, versioned.version);
  }
  return versioned.data as T;
}

/**
 * Schema compatibility check result
 */
export interface CompatibilityResult {
  compatible: boolean;
  currentVersion: number;
  dataVersion: number;
  migrationPath: Migration[];
  warnings: string[];
}

/**
 * Check schema compatibility
 */
export function checkCompatibility(dataVersion: number): CompatibilityResult {
  const path = getMigrationPath(dataVersion);
  const warnings: string[] = [];

  // Warn if major version difference
  if (SCHEMA_VERSION - dataVersion > 5) {
    warnings.push('Large version gap detected. Consider a full data refresh.');
  }

  // Check for non-reversible migrations
  const nonReversible = path.filter((m) => !m.rollback);
  if (nonReversible.length > 0) {
    warnings.push(`${nonReversible.length} migration(s) are not reversible.`);
  }

  return {
    compatible: true, // Currently all versions are forward-compatible
    currentVersion: SCHEMA_VERSION,
    dataVersion,
    migrationPath: path,
    warnings,
  };
}
