/**
 * Schema Types for Foundation Query Engine
 *
 * Defines types for schema definitions including tables,
 * measures, dimensions, and relationships.
 *
 * Uses const objects with derived types pattern.
 *
 * @module types/schema
 */

import type {
  MemberRef,
  SqlTableName as TableName,
} from '@open-zentra/foundation-data-model';

import type { Aggregation } from './aggregation';
import type { JoinType } from './join';
import type { MeasureFormatType } from './measure';
import type { TimeGranularity } from './time';

// =============================================================================
// MEASURE DATA TYPES - Const object pattern
// =============================================================================

/**
 * Data types for measure results
 */
export const MEASURE_DATA_TYPES = {
  /** Integer number */
  INTEGER: 'integer',
  /** Floating-point number */
  FLOAT: 'float',
  /** String value */
  STRING: 'string',
  /** Boolean value */
  BOOLEAN: 'boolean',
} as const;

/**
 * Measure data type derived from MEASURE_DATA_TYPES
 */
export type MeasureDataType = (typeof MEASURE_DATA_TYPES)[keyof typeof MEASURE_DATA_TYPES];

// =============================================================================
// DIMENSION TYPES - Const object pattern
// =============================================================================

/**
 * Types of dimensions
 */
export const DIMENSION_TYPES = {
  /** String/categorical dimension */
  STRING: 'string',
  /** Numeric dimension */
  NUMBER: 'number',
  /** Boolean dimension */
  BOOLEAN: 'boolean',
  /** Date/time dimension */
  TIME: 'time',
  /** Geographic dimension */
  GEO: 'geo',
} as const;

/**
 * Dimension type derived from DIMENSION_TYPES
 */
export type DimensionType = (typeof DIMENSION_TYPES)[keyof typeof DIMENSION_TYPES];

// =============================================================================
// MEMBER VISIBILITY - Const object pattern
// =============================================================================

/**
 * Member visibility levels
 */
export const MEMBER_VISIBILITY = {
  /** Visible in all contexts */
  PUBLIC: 'public',
  /** Hidden from UI but can be queried */
  HIDDEN: 'hidden',
  /** Internal use only */
  INTERNAL: 'internal',
} as const;

/**
 * Member visibility type derived from MEMBER_VISIBILITY
 */
export type MemberVisibility = (typeof MEMBER_VISIBILITY)[keyof typeof MEMBER_VISIBILITY];

// =============================================================================
// RELATIONSHIP TYPES - Const object pattern
// =============================================================================

/**
 * Relationship cardinalities for schema joins.
 */
export const RELATIONSHIP_CARDINALITIES = {
  ONE_TO_ONE: 'one_to_one',
  ONE_TO_MANY: 'one_to_many',
  MANY_TO_ONE: 'many_to_one',
} as const;

/**
 * Relationship cardinality type derived from RELATIONSHIP_CARDINALITIES.
 */
export type RelationshipCardinality =
  (typeof RELATIONSHIP_CARDINALITIES)[keyof typeof RELATIONSHIP_CARDINALITIES];

/**
 * JoinDefinition type derived from JOIN_TYPES.
 */
export type JoinDefinitionType = JoinType;

/**
 * Relationship values for JoinDefinition.
 */
export const JOIN_RELATIONSHIP_CARDINALITIES = {
  ONE_TO_ONE: 'one-to-one',
  ONE_TO_MANY: 'one-to-many',
  MANY_TO_ONE: 'many-to-one',
} as const;

/**
 * JoinDefinition relationship derived from JOIN_RELATIONSHIP_CARDINALITIES.
 */
export type JoinRelationshipCardinality =
  (typeof JOIN_RELATIONSHIP_CARDINALITIES)[keyof typeof JOIN_RELATIONSHIP_CARDINALITIES];

/**
 * Mapping from schema relationship cardinalities (underscore format: `one_to_one`)
 * to join relationship cardinalities (hyphen format: `one-to-one`).
 *
 * Use this when converting between the two cardinality representations.
 */
export const CARDINALITY_TO_JOIN_CARDINALITY: Readonly<
  Record<RelationshipCardinality, JoinRelationshipCardinality>
> = {
  [RELATIONSHIP_CARDINALITIES.ONE_TO_ONE]: JOIN_RELATIONSHIP_CARDINALITIES.ONE_TO_ONE,
  [RELATIONSHIP_CARDINALITIES.ONE_TO_MANY]: JOIN_RELATIONSHIP_CARDINALITIES.ONE_TO_MANY,
  [RELATIONSHIP_CARDINALITIES.MANY_TO_ONE]: JOIN_RELATIONSHIP_CARDINALITIES.MANY_TO_ONE,
} as const;

// =============================================================================
// SCHEMA STRUCTURES
// =============================================================================

/**
 * Column definition for a table
 */
export interface ColumnDefinition {
  /** Column name in the source */
  readonly name: string;
  /** SQL type */
  readonly type: string;
  /** Whether the column is nullable */
  readonly nullable?: boolean;
  /** Default value */
  readonly defaultValue?: unknown;
  /** Whether this is a primary key */
  readonly primaryKey?: boolean;
}

/**
 * Dimension definition in a table
 */
export interface DimensionDefinition {
  /** Dimension type */
  readonly type: DimensionType;
  /** SQL expression or column name */
  readonly sql: string;
  /** Human-readable title */
  readonly title?: string;
  /** Description */
  readonly description?: string;
  /** Whether this is a primary key */
  readonly primaryKey?: boolean;
  /** Visibility level */
  readonly visibility?: MemberVisibility;
  /** Meta information */
  readonly meta?: Record<string, unknown>;
}

/**
 * Time dimension definition (extends dimension)
 */
export interface TimeDimensionDefinition extends DimensionDefinition {
  /** Dimension type is always 'time' */
  readonly type: typeof DIMENSION_TYPES.TIME;
  /** Default granularity */
  readonly granularity?: TimeGranularity;
  /** Supported granularities */
  readonly granularities?: ReadonlyArray<TimeGranularity>;
}

/**
 * Measure definition in a table
 */
export interface MeasureDefinition {
  /** Aggregation function */
  readonly type: Aggregation;
  /** SQL expression for the measure */
  readonly sql: string;
  /** Human-readable title */
  readonly title?: string;
  /** Description */
  readonly description?: string;
  /** Data type of the result */
  readonly dataType?: MeasureDataType;
  /** Format specification */
  readonly format?: MeasureFormatType;
  /** Filter to apply before aggregation */
  readonly filters?: ReadonlyArray<string>;
  /** Drill-down members */
  readonly drillMembers?: ReadonlyArray<MemberRef>;
  /** Visibility level */
  readonly visibility?: MemberVisibility;
  /** Meta information */
  readonly meta?: Record<string, unknown>;
}

/**
 * Relationship between tables
 */
export interface RelationshipDefinition {
  /** Target table name */
  readonly table: TableName | string;
  /** SQL join condition */
  readonly sql: string;
  /** Relationship type */
  readonly relationship: RelationshipCardinality;
  /** Join type to use */
  readonly joinType?: JoinType;
}

/**
 * Pre-aggregation definition for performance optimization
 */
export interface PreAggregationDefinition {
  /** Pre-aggregation name */
  readonly name: string;
  /** Measures to include */
  readonly measures?: ReadonlyArray<string>;
  /** Dimensions to include */
  readonly dimensions?: ReadonlyArray<string>;
  /** Time dimension for partitioning */
  readonly timeDimension?: string;
  /** Granularity for time partitioning */
  readonly granularity?: TimeGranularity;
  /** Partition granularity */
  readonly partitionGranularity?: TimeGranularity;
  /** Refresh strategy */
  readonly refreshKey?: {
    readonly sql?: string;
    readonly every?: string;
  };
  /** Indexes to create */
  readonly indexes?: ReadonlyArray<{
    readonly columns: ReadonlyArray<string>;
  }>;
}

/**
 * Join definition for relationships between tables
 */
export interface JoinDefinition {
  /** Target table to join */
  readonly table: string;
  /** Join condition SQL expression */
  readonly sql: string;
  /** Join type */
  readonly type?: JoinDefinitionType;
  /** Whether this is a one-to-one relationship */
  readonly relationship?: JoinRelationshipCardinality;
}

/**
 * Table definition in the schema
 */
export interface TableDefinition {
  /** Table name */
  readonly name: string;
  /** SQL table expression (can be a subquery) */
  readonly sql: string;
  /** Human-readable title */
  readonly title?: string;
  /** Description */
  readonly description?: string;
  /** Column definitions */
  readonly columns?: Record<string, ColumnDefinition>;
  /** Dimension definitions */
  readonly dimensions?: Record<string, DimensionDefinition | TimeDimensionDefinition>;
  /** Measure definitions */
  readonly measures?: Record<string, MeasureDefinition>;
  /** Relationships to other tables */
  readonly relationships?: Record<string, RelationshipDefinition>;
  /** Pre-aggregation definitions */
  readonly preAggregations?: Record<string, PreAggregationDefinition>;
  /** Joins to other tables */
  readonly joins?: Record<string, JoinDefinition>;
  /** Data source identifier */
  readonly dataSource?: string;
  /** Refresh key for pre-aggregations */
  readonly refreshKey?: {
    readonly sql?: string;
    readonly every?: string;
  };
  /** Meta information */
  readonly meta?: Record<string, unknown>;
}

/**
 * Complete schema definition
 */
export interface SchemaDefinition {
  /** Schema name */
  readonly name: string;
  /** Schema version */
  readonly version: string;
  /** Table definitions */
  readonly tables: Record<string, TableDefinition>;
  /** Default timezone for the schema */
  readonly defaultTimezone?: string;
  /** Default data source */
  readonly defaultDataSource?: string;
  /** Meta information */
  readonly meta?: Record<string, unknown>;
}

// =============================================================================
// TYPE GUARDS
// =============================================================================

/**
 * Check if a value is a valid dimension type
 */
export const isDimensionType = (value: unknown): value is DimensionType =>
  typeof value === 'string' && Object.values(DIMENSION_TYPES).includes(value as DimensionType);

/**
 * Check if a dimension is a time dimension
 */
export const isTimeDimension = (
  dimension: DimensionDefinition | TimeDimensionDefinition,
): dimension is TimeDimensionDefinition => dimension.type === DIMENSION_TYPES.TIME;

/**
 * Check if a value is a valid member visibility
 */
export const isMemberVisibility = (value: unknown): value is MemberVisibility =>
  typeof value === 'string' && Object.values(MEMBER_VISIBILITY).includes(value as MemberVisibility);

// =============================================================================
// SCHEMA HELPERS
// =============================================================================

/**
 * Get all measure names from a table definition
 */
export const getTableMeasures = (table: TableDefinition): ReadonlyArray<string> =>
  table.measures ? Object.keys(table.measures) : [];

/**
 * Get all dimension names from a table definition
 */
export const getTableDimensions = (table: TableDefinition): ReadonlyArray<string> =>
  table.dimensions ? Object.keys(table.dimensions) : [];

/**
 * Get all visible members from a table
 */
export const getVisibleMembers = (
  table: TableDefinition,
): {
  measures: ReadonlyArray<string>;
  dimensions: ReadonlyArray<string>;
} => {
  const visibleMeasures = table.measures
    ? Object.entries(table.measures)
        .filter(([, def]) => def.visibility !== MEMBER_VISIBILITY.HIDDEN)
        .map(([name]) => name)
    : [];

  const visibleDimensions = table.dimensions
    ? Object.entries(table.dimensions)
        .filter(([, def]) => def.visibility !== MEMBER_VISIBILITY.HIDDEN)
        .map(([name]) => name)
    : [];

  return { measures: visibleMeasures, dimensions: visibleDimensions };
};

/**
 * Create a member reference from table and member name
 */
export const createMemberRef = (tableName: string, memberName: string): MemberRef =>
  `${tableName}.${memberName}` as MemberRef;
