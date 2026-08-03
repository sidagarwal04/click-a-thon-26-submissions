/**
 * Schema Registry for Foundation Query Engine
 *
 * Provides schema management, member resolution, and validation.
 * Follows the singleton pattern from foundation libraries.
 *
 * NOTE: This is distinct from TableRegistry in data-layer:
 * - **TableRegistry** (data-layer): API descriptors, conflict strategies, cache config
 *   Used for: HTTP API calls, offline sync, cache management
 *
 * - **SchemaRegistry** (query-engine): Dimension/measure definitions, validation rules
 *   Used for: Query validation, member resolution, type checking
 *
 * Both registries serve different purposes and may reference the same tables
 * but with different metadata. TableRegistry is required; SchemaRegistry is
 * optional and provides enhanced validation for analytics queries.
 *
 * @module schema/registry
 */

import type {
  MemberRef,
  SqlTableName as TableName,
} from '@open-zentra/foundation-data-model';
import {
  MemberRef as MemberRefUtil,
  SqlTableName as TableNameUtil,
} from '@open-zentra/foundation-data-model';
import { createLogger, DisposedError, type IDisposable } from '@open-zentra/foundation-utils';

import type {
  DimensionDefinition,
  MeasureDefinition,
  SchemaDefinition,
  TableDefinition,
  TimeDimensionDefinition,
} from '../types/schema-definition';
import { parseMemberRef } from '../utils/member-ref';

const logger = createLogger('SchemaRegistry');

// =============================================================================
// MEMBER TYPES - Const object pattern
// =============================================================================

/**
 * Types of schema members
 */
export const MEMBER_TYPES = {
  /** Measure (aggregation) */
  MEASURE: 'measure',
  /** Dimension (grouping/filtering) */
  DIMENSION: 'dimension',
} as const;

/**
 * Member type derived from MEMBER_TYPES
 */
export type MemberType = (typeof MEMBER_TYPES)[keyof typeof MEMBER_TYPES];

// =============================================================================
// MEMBER RESOLUTION
// =============================================================================

interface BaseMemberResolution {
  /** Table name */
  readonly table: string;
  /** Member name */
  readonly name: string;
  /** Full member reference */
  readonly ref: MemberRef;
}

interface MeasureMemberResolution extends BaseMemberResolution {
  /** Member type (measure) */
  readonly type: typeof MEMBER_TYPES.MEASURE;
  /** Member definition */
  readonly definition: MeasureDefinition;
}

interface DimensionMemberResolution extends BaseMemberResolution {
  /** Member type (dimension) */
  readonly type: typeof MEMBER_TYPES.DIMENSION;
  /** Member definition */
  readonly definition: DimensionDefinition | TimeDimensionDefinition;
}

/**
 * Resolved member information
 */
export type MemberResolution = MeasureMemberResolution | DimensionMemberResolution;

/**
 * Schema validation status with errors and warnings
 *
 * This is specific to schema validation in query-engine.
 * For general validation, use `ValidationResult` from `@open-zentra/foundation-data-model`.
 *
 * Named "Status" to avoid confusion with `ValidationResult` from foundation-data-model.
 */
export interface SchemaValidationStatus {
  /** Whether validation passed (no errors) */
  readonly valid: boolean;
  /** Error messages (empty if valid) */
  readonly errors: ReadonlyArray<string>;
  /** Warning messages (non-blocking issues) */
  readonly warnings: ReadonlyArray<string>;
}

// =============================================================================
// CUSTOM ERRORS
// =============================================================================

/**
 * Types of schema elements for error construction.
 */
export const SCHEMA_ELEMENT_TYPES = {
  TABLE: 'table',
  MEASURE: 'measure',
  DIMENSION: 'dimension',
  MEMBER: 'member',
} as const;

type SchemaElementType = (typeof SCHEMA_ELEMENT_TYPES)[keyof typeof SCHEMA_ELEMENT_TYPES];

/**
 * Error thrown when a schema element is not found
 */
export class SchemaNotFoundError extends Error {
  readonly code = 'SCHEMA_NOT_FOUND' as const;
  readonly elementType: SchemaElementType;
  readonly elementName: string;

  constructor(elementType: SchemaElementType, elementName: string) {
    super(`${elementType} '${elementName}' not found in schema`);
    this.name = 'SchemaNotFoundError';
    this.elementType = elementType;
    this.elementName = elementName;
  }
}

/**
 * Error thrown when schema validation fails
 */
export class SchemaValidationError extends Error {
  readonly code = 'SCHEMA_VALIDATION_FAILED' as const;
  readonly errors: ReadonlyArray<string>;

  constructor(errors: ReadonlyArray<string>) {
    super(`Schema validation failed: ${errors.join('; ')}`);
    this.name = 'SchemaValidationError';
    this.errors = errors;
  }
}

// =============================================================================
// SCHEMA REGISTRY CLASS
// =============================================================================

/**
 * Schema Registry
 *
 * Manages schema definitions and provides member resolution.
 * Uses caching for performance optimization.
 * Implements IDisposable for proper resource cleanup.
 */
export class SchemaRegistry implements IDisposable {
  private readonly schema: SchemaDefinition;
  private readonly tableMap: Map<string, TableDefinition>;
  private readonly memberCache: Map<string, MemberResolution>;
  private readonly debug: boolean;
  private _isDisposed = false;

  constructor(schema: SchemaDefinition, debug = false) {
    this.schema = schema;
    this.tableMap = new Map();
    this.memberCache = new Map();
    this.debug = debug;
    this.initializeMaps();

    if (this.debug) {
      logger.debug('SchemaRegistry initialized', {
        name: schema.name,
        version: schema.version,
        tableCount: this.tableMap.size,
      });
    }
  }

  /**
   * Check if the registry is disposed.
   */
  get isDisposed(): boolean {
    return this._isDisposed;
  }

  /**
   * Dispose of resources (clear caches).
   */
  dispose(): void {
    if (this._isDisposed) return;
    this._isDisposed = true;
    this.tableMap.clear();
    this.memberCache.clear();
    if (this.debug) {
      logger.debug('SchemaRegistry disposed');
    }
  }

  /**
   * Ensure the registry is not disposed before use.
   */
  private ensureNotDisposed(): void {
    if (this._isDisposed) {
      throw new DisposedError('SchemaRegistry');
    }
  }

  /**
   * Initialize internal maps from schema
   */
  private initializeMaps = (): void => {
    for (const [name, table] of Object.entries(this.schema.tables)) {
      this.tableMap.set(name, table);
    }
  };

  // ---------------------------------------------------------------------------
  // Schema Information
  // ---------------------------------------------------------------------------

  /**
   * Get the schema definition
   */
  getSchema = (): SchemaDefinition => {
    this.ensureNotDisposed();
    return this.schema;
  };

  /**
   * Get the schema name
   */
  getName = (): string => {
    this.ensureNotDisposed();
    return this.schema.name;
  };

  /**
   * Get the schema version
   */
  getVersion = (): string => {
    this.ensureNotDisposed();
    return this.schema.version;
  };

  /**
   * Get the default timezone
   */
  getDefaultTimezone = (): string | undefined => {
    this.ensureNotDisposed();
    return this.schema.defaultTimezone;
  };

  // ---------------------------------------------------------------------------
  // Table Operations
  // ---------------------------------------------------------------------------

  /**
   * Get all table names
   */
  getTableNames = (): ReadonlyArray<TableName> => {
    this.ensureNotDisposed();
    return Array.from(this.tableMap.keys()).map(TableNameUtil.from);
  };

  /**
   * Check if a table exists
   */
  hasTable = (name: string): boolean => {
    this.ensureNotDisposed();
    return this.tableMap.has(name);
  };

  /**
   * Get a table definition (returns null if not found)
   */
  getTable = (name: string): TableDefinition | null => {
    this.ensureNotDisposed();
    return this.tableMap.get(name) ?? null;
  };

  /**
   * Get a table definition (throws if not found)
   */
  getTableOrThrow = (name: string): TableDefinition => {
    const table = this.getTable(name);
    if (!table) {
      throw new SchemaNotFoundError(SCHEMA_ELEMENT_TYPES.TABLE, name);
    }
    return table;
  };

  // ---------------------------------------------------------------------------
  // Member Resolution
  // ---------------------------------------------------------------------------

  /**
   * Resolve a member reference to its definition
   */
  resolveMember = (memberRef: MemberRef | string): MemberResolution | null => {
    this.ensureNotDisposed();
    const rawMemberRef = String(memberRef);

    // Check cache first
    const cached = this.memberCache.get(rawMemberRef);
    if (cached) {
      return cached;
    }

    // Parse the reference
    const parsed = parseMemberRef(rawMemberRef);
    if (!parsed) {
      return null;
    }

    const normalizedRef = MemberRefUtil.create(parsed.table, parsed.column);
    const table = this.getTable(parsed.table);
    if (!table) {
      return null;
    }

    // Check measures first
    const measure = table.measures?.[parsed.column];
    if (measure) {
      const resolution: MeasureMemberResolution = {
        type: MEMBER_TYPES.MEASURE,
        table: parsed.table,
        name: parsed.column,
        ref: normalizedRef,
        definition: measure,
      };
      this.memberCache.set(rawMemberRef, resolution);
      return resolution;
    }

    // Then check dimensions
    const dimension = table.dimensions?.[parsed.column];
    if (dimension) {
      const resolution: DimensionMemberResolution = {
        type: MEMBER_TYPES.DIMENSION,
        table: parsed.table,
        name: parsed.column,
        ref: normalizedRef,
        definition: dimension,
      };
      this.memberCache.set(rawMemberRef, resolution);
      return resolution;
    }

    return null;
  };

  /**
   * Resolve a member reference (throws if not found)
   */
  resolveMemberOrThrow = (memberRef: MemberRef | string): MemberResolution => {
    const resolved = this.resolveMember(memberRef);
    if (!resolved) {
      throw new SchemaNotFoundError(SCHEMA_ELEMENT_TYPES.MEMBER, String(memberRef));
    }
    return resolved;
  };

  /**
   * Get a measure definition
   */
  getMeasure = (memberRef: MemberRef | string): MeasureDefinition | null => {
    const resolved = this.resolveMember(memberRef);
    if (resolved?.type === MEMBER_TYPES.MEASURE) {
      return resolved.definition;
    }
    return null;
  };

  /**
   * Get a dimension definition
   */
  getDimension = (
    memberRef: MemberRef | string,
  ): DimensionDefinition | TimeDimensionDefinition | null => {
    const resolved = this.resolveMember(memberRef);
    if (resolved?.type === MEMBER_TYPES.DIMENSION) {
      return resolved.definition;
    }
    return null;
  };

  // ---------------------------------------------------------------------------
  // Bulk Operations
  // ---------------------------------------------------------------------------

  /**
   * Get all measures from a table
   */
  getTableMeasures = (tableName: string): ReadonlyArray<MemberResolution> => {
    const table = this.getTable(tableName);
    if (!table?.measures) {
      return [];
    }

    return Object.entries(table.measures).map(([name, def]) => ({
      type: MEMBER_TYPES.MEASURE,
      table: tableName,
      name,
      ref: MemberRefUtil.create(tableName, name),
      definition: def,
    }));
  };

  /**
   * Get all dimensions from a table
   */
  getTableDimensions = (tableName: string): ReadonlyArray<MemberResolution> => {
    const table = this.getTable(tableName);
    if (!table?.dimensions) {
      return [];
    }

    return Object.entries(table.dimensions).map(([name, def]) => ({
      type: MEMBER_TYPES.DIMENSION,
      table: tableName,
      name,
      ref: MemberRefUtil.create(tableName, name),
      definition: def,
    }));
  };

  /**
   * Get all members from a table
   */
  getTableMembers = (tableName: string): ReadonlyArray<MemberResolution> => [
    ...this.getTableMeasures(tableName),
    ...this.getTableDimensions(tableName),
  ];

  // ---------------------------------------------------------------------------
  // Validation
  // ---------------------------------------------------------------------------

  /**
   * Validate that all member references exist
   */
  validateMembers = (memberRefs: ReadonlyArray<MemberRef | string>): SchemaValidationStatus => {
    const errors: string[] = [];
    const warnings: string[] = [];

    for (const ref of memberRefs) {
      const resolved = this.resolveMember(ref);
      if (!resolved) {
        errors.push(`Member '${ref}' not found in schema`);
      }
    }

    return {
      valid: errors.length === 0,
      errors,
      warnings,
    };
  };

  /**
   * Validate that a table has the required members
   */
  validateTableMembers = (
    tableName: string,
    required: {
      measures?: ReadonlyArray<string>;
      dimensions?: ReadonlyArray<string>;
    },
  ): SchemaValidationStatus => {
    const errors: string[] = [];
    const warnings: string[] = [];
    const table = this.getTable(tableName);

    if (!table) {
      errors.push(`Table '${tableName}' not found`);
      return { valid: false, errors, warnings };
    }

    // Check required measures
    if (required.measures) {
      for (const measureName of required.measures) {
        if (!table.measures?.[measureName]) {
          errors.push(`Required measure '${measureName}' not found in table '${tableName}'`);
        }
      }
    }

    // Check required dimensions
    if (required.dimensions) {
      for (const dimensionName of required.dimensions) {
        if (!table.dimensions?.[dimensionName]) {
          errors.push(`Required dimension '${dimensionName}' not found in table '${tableName}'`);
        }
      }
    }

    return {
      valid: errors.length === 0,
      errors,
      warnings,
    };
  };

  // ---------------------------------------------------------------------------
  // Cache Management
  // ---------------------------------------------------------------------------

  /**
   * Clear the member cache
   */
  clearCache = (): void => {
    this.memberCache.clear();
    if (this.debug) {
      logger.debug('Member cache cleared');
    }
  };

  /**
   * Get cache statistics
   */
  getCacheStats = (): { size: number } => ({
    size: this.memberCache.size,
  });
}

// =============================================================================
// FACTORY FUNCTION
// =============================================================================

/**
 * Create a new SchemaRegistry instance
 */
export const createSchemaRegistry = (schema: SchemaDefinition, debug = false): SchemaRegistry =>
  new SchemaRegistry(schema, debug);
