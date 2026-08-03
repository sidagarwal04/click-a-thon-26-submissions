/**
 * Schema Builders for Foundation Query Engine
 *
 * Provides fluent builder APIs for creating schema definitions.
 *
 * @module schema/builders
 */

import type { Mutable } from '@open-zentra/foundation-data-model';
import {
  MemberRef as MemberRefUtil,
  SqlTableName as TableNameUtil,
} from '@open-zentra/foundation-data-model';

import { AGGREGATIONS, type Aggregation } from '../types/aggregation';
import { JOIN_TYPES, type JoinType } from '../types/join';
import { type MeasureFormatType } from '../types/measure';
import {
  CARDINALITY_TO_JOIN_CARDINALITY,
  DIMENSION_TYPES,
  MEMBER_VISIBILITY,
  type DimensionDefinition,
  type DimensionType,
  type JoinDefinition,
  type MeasureDataType,
  type MeasureDefinition,
  type MemberVisibility,
  type PreAggregationDefinition,
  type RelationshipDefinition,
  type SchemaDefinition,
  type TableDefinition,
  type TimeDimensionDefinition,
} from '../types/schema-definition';
import { type TimeGranularity } from '../types/time';

// =============================================================================
// MEASURE BUILDER
// =============================================================================

/**
 * Builder for creating measure definitions.
 */
export class MeasureBuilder {
  private readonly definition: Mutable<Partial<MeasureDefinition>> = {};

  constructor(aggregation: Aggregation, sql: string) {
    this.definition.type = aggregation;
    this.definition.sql = sql;
  }

  /** Set the measure title. */
  title = (title: string): MeasureBuilder => {
    this.definition.title = title;
    return this;
  };

  /** Set the measure description. */
  description = (description: string): MeasureBuilder => {
    this.definition.description = description;
    return this;
  };

  /** Set the measure data type. */
  dataType = (dataType: MeasureDataType): MeasureBuilder => {
    this.definition.dataType = dataType;
    return this;
  };

  /** Set the measure format. */
  format = (format: MeasureFormatType): MeasureBuilder => {
    this.definition.format = format;
    return this;
  };

  /** Add SQL filters applied pre-aggregation. */
  filters = (filters: ReadonlyArray<string>): MeasureBuilder => {
    this.definition.filters = [...filters];
    return this;
  };

  /** Set drill-down members. */
  drillMembers = (members: ReadonlyArray<string>): MeasureBuilder => {
    this.definition.drillMembers = members.map(MemberRefUtil.from);
    return this;
  };

  /** Set visibility for this measure. */
  visibility = (visibility: MemberVisibility): MeasureBuilder => {
    this.definition.visibility = visibility;
    return this;
  };

  /** Hide the measure from UI. */
  hidden = (): MeasureBuilder => {
    this.definition.visibility = MEMBER_VISIBILITY.HIDDEN;
    return this;
  };

  /** Attach metadata to the measure. */
  meta = (meta: Record<string, unknown>): MeasureBuilder => {
    this.definition.meta = meta;
    return this;
  };

  /** Build the measure definition. */
  build = (): MeasureDefinition => {
    if (!this.definition.type || !this.definition.sql) {
      throw new Error('Measure definition requires both aggregation type and SQL');
    }

    return {
      type: this.definition.type,
      sql: this.definition.sql,
      title: this.definition.title,
      description: this.definition.description,
      dataType: this.definition.dataType,
      format: this.definition.format,
      filters: this.definition.filters,
      drillMembers: this.definition.drillMembers,
      visibility: this.definition.visibility,
      meta: this.definition.meta,
    };
  };
}

// =============================================================================
// DIMENSION BUILDER
// =============================================================================

/**
 * Builder for creating dimension definitions.
 */
export class DimensionBuilder {
  private readonly definition: Mutable<Partial<DimensionDefinition>> = {};

  constructor(type: DimensionType, sql: string) {
    this.definition.type = type;
    this.definition.sql = sql;
  }

  /** Set the dimension title. */
  title = (title: string): DimensionBuilder => {
    this.definition.title = title;
    return this;
  };

  /** Set the dimension description. */
  description = (description: string): DimensionBuilder => {
    this.definition.description = description;
    return this;
  };

  /** Mark as primary key. */
  primaryKey = (isPrimary = true): DimensionBuilder => {
    this.definition.primaryKey = isPrimary;
    return this;
  };

  /** Set visibility. */
  visibility = (visibility: MemberVisibility): DimensionBuilder => {
    this.definition.visibility = visibility;
    return this;
  };

  /** Hide the dimension from UI. */
  hidden = (): DimensionBuilder => {
    this.definition.visibility = MEMBER_VISIBILITY.HIDDEN;
    return this;
  };

  /** Attach metadata. */
  meta = (meta: Record<string, unknown>): DimensionBuilder => {
    this.definition.meta = meta;
    return this;
  };

  /** Build the dimension definition. */
  build = (): DimensionDefinition => {
    if (!this.definition.type || !this.definition.sql) {
      throw new Error('Dimension definition requires both type and SQL');
    }

    return {
      type: this.definition.type,
      sql: this.definition.sql,
      title: this.definition.title,
      description: this.definition.description,
      primaryKey: this.definition.primaryKey,
      visibility: this.definition.visibility,
      meta: this.definition.meta,
    };
  };
}

// =============================================================================
// TIME DIMENSION BUILDER
// =============================================================================

/**
 * Builder for creating time dimension definitions.
 */
export class TimeDimensionBuilder {
  private readonly definition: Mutable<Partial<TimeDimensionDefinition>> = {
    type: DIMENSION_TYPES.TIME,
  };

  constructor(sql: string) {
    this.definition.sql = sql;
  }

  /** Set the dimension title. */
  title = (title: string): TimeDimensionBuilder => {
    this.definition.title = title;
    return this;
  };

  /** Set the dimension description. */
  description = (description: string): TimeDimensionBuilder => {
    this.definition.description = description;
    return this;
  };

  /** Set default granularity. */
  granularity = (granularity: TimeGranularity): TimeDimensionBuilder => {
    this.definition.granularity = granularity;
    return this;
  };

  /** Set supported granularities. */
  granularities = (granularities: ReadonlyArray<TimeGranularity>): TimeDimensionBuilder => {
    this.definition.granularities = [...granularities];
    return this;
  };

  /** Mark as primary key. */
  primaryKey = (isPrimary = true): TimeDimensionBuilder => {
    this.definition.primaryKey = isPrimary;
    return this;
  };

  /** Set visibility. */
  visibility = (visibility: MemberVisibility): TimeDimensionBuilder => {
    this.definition.visibility = visibility;
    return this;
  };

  /** Attach metadata. */
  meta = (meta: Record<string, unknown>): TimeDimensionBuilder => {
    this.definition.meta = meta;
    return this;
  };

  /** Build the time dimension definition. */
  build = (): TimeDimensionDefinition => {
    if (!this.definition.sql) {
      throw new Error('Time dimension definition requires SQL');
    }

    return {
      type: DIMENSION_TYPES.TIME,
      sql: this.definition.sql,
      title: this.definition.title,
      description: this.definition.description,
      granularity: this.definition.granularity,
      granularities: this.definition.granularities,
      primaryKey: this.definition.primaryKey,
      visibility: this.definition.visibility,
      meta: this.definition.meta,
    };
  };
}

// =============================================================================
// TABLE BUILDER
// =============================================================================

/**
 * Builder for creating table definitions.
 */
export class TableBuilder {
  private readonly definition: Mutable<Partial<TableDefinition>> = {};
  private readonly measuresMap: Record<string, MeasureDefinition> = {};
  private readonly dimensionsMap: Record<string, DimensionDefinition | TimeDimensionDefinition> =
    {};
  private readonly joinsMap: Record<string, JoinDefinition> = {};
  private readonly preAggregationsMap: Record<string, PreAggregationDefinition> = {};

  constructor(name: string, sql: string) {
    this.definition.name = name;
    this.definition.sql = sql;
  }

  /** Set table title. */
  title = (title: string): TableBuilder => {
    this.definition.title = title;
    return this;
  };

  /** Set table description. */
  description = (description: string): TableBuilder => {
    this.definition.description = description;
    return this;
  };

  /** Set source identifier. */
  dataSource = (dataSource: string): TableBuilder => {
    this.definition.dataSource = dataSource;
    return this;
  };

  /** Add a measure definition. */
  addMeasure = (name: string, builder: MeasureBuilder | MeasureDefinition): TableBuilder => {
    this.measuresMap[name] = 'build' in builder ? builder.build() : builder;
    return this;
  };

  /** Add COUNT(*) measure. */
  count = (name: string, title?: string): TableBuilder => {
    const builder = new MeasureBuilder(AGGREGATIONS.COUNT, '*');
    if (title) {
      builder.title(title);
    }
    this.measuresMap[name] = builder.build();
    return this;
  };

  /** Add SUM(column) measure. */
  sum = (name: string, column: string, title?: string): TableBuilder => {
    const builder = new MeasureBuilder(AGGREGATIONS.SUM, column);
    if (title) {
      builder.title(title);
    }
    this.measuresMap[name] = builder.build();
    return this;
  };

  /** Add AVG(column) measure. */
  avg = (name: string, column: string, title?: string): TableBuilder => {
    const builder = new MeasureBuilder(AGGREGATIONS.AVG, column);
    if (title) {
      builder.title(title);
    }
    this.measuresMap[name] = builder.build();
    return this;
  };

  /** Add a dimension definition. */
  addDimension = (
    name: string,
    builder:
      | DimensionBuilder
      | TimeDimensionBuilder
      | DimensionDefinition
      | TimeDimensionDefinition,
  ): TableBuilder => {
    this.dimensionsMap[name] = 'build' in builder ? builder.build() : builder;
    return this;
  };

  /** Add string dimension. */
  string = (name: string, sql: string, title?: string): TableBuilder => {
    const builder = new DimensionBuilder(DIMENSION_TYPES.STRING, sql);
    if (title) {
      builder.title(title);
    }
    this.dimensionsMap[name] = builder.build();
    return this;
  };

  /** Add numeric dimension. */
  number = (name: string, sql: string, title?: string): TableBuilder => {
    const builder = new DimensionBuilder(DIMENSION_TYPES.NUMBER, sql);
    if (title) {
      builder.title(title);
    }
    this.dimensionsMap[name] = builder.build();
    return this;
  };

  /** Add boolean dimension. */
  boolean = (name: string, sql: string, title?: string): TableBuilder => {
    const builder = new DimensionBuilder(DIMENSION_TYPES.BOOLEAN, sql);
    if (title) {
      builder.title(title);
    }
    this.dimensionsMap[name] = builder.build();
    return this;
  };

  /** Add time dimension. */
  time = (name: string, sql: string, title?: string): TableBuilder => {
    const builder = new TimeDimensionBuilder(sql);
    if (title) {
      builder.title(title);
    }
    this.dimensionsMap[name] = builder.build();
    return this;
  };

  /** Add relationship to another table. */
  join = (
    name: string,
    targetTable: string,
    sql: string,
    relationship: RelationshipDefinition['relationship'],
    joinType: JoinType = JOIN_TYPES.LEFT,
  ): TableBuilder => {
    this.joinsMap[name] = {
      table: TableNameUtil.from(targetTable),
      sql,
      relationship: CARDINALITY_TO_JOIN_CARDINALITY[relationship],
      type: joinType,
    };
    return this;
  };

  /** Add pre-aggregation. */
  preAggregation = (name: string, config: Omit<PreAggregationDefinition, 'name'>): TableBuilder => {
    this.preAggregationsMap[name] = { name, ...config };
    return this;
  };

  /** Configure refresh key. */
  refreshKey = (config: { sql?: string; every?: string }): TableBuilder => {
    this.definition.refreshKey = config;
    return this;
  };

  /** Attach metadata. */
  meta = (meta: Record<string, unknown>): TableBuilder => {
    this.definition.meta = meta;
    return this;
  };

  /** Build table definition. */
  build = (): TableDefinition => {
    if (!this.definition.name || !this.definition.sql) {
      throw new Error('Table definition requires both name and SQL');
    }

    return {
      name: this.definition.name,
      sql: this.definition.sql,
      title: this.definition.title,
      description: this.definition.description,
      columns: this.definition.columns,
      dimensions: Object.keys(this.dimensionsMap).length > 0 ? this.dimensionsMap : undefined,
      measures: Object.keys(this.measuresMap).length > 0 ? this.measuresMap : undefined,
      relationships: this.definition.relationships,
      preAggregations:
        Object.keys(this.preAggregationsMap).length > 0 ? this.preAggregationsMap : undefined,
      joins: Object.keys(this.joinsMap).length > 0 ? this.joinsMap : undefined,
      dataSource: this.definition.dataSource,
      refreshKey: this.definition.refreshKey,
      meta: this.definition.meta,
    };
  };
}

// =============================================================================
// SCHEMA BUILDER
// =============================================================================

/**
 * Builder for creating schema definitions.
 */
export class SchemaBuilder {
  private readonly definition: Mutable<Partial<SchemaDefinition>> = {};
  private readonly tablesMap: Record<string, TableDefinition> = {};

  constructor(name: string, version = '1.0.0') {
    this.definition.name = name;
    this.definition.version = version;
  }

  /** Set default timezone. */
  defaultTimezone = (timezone: string): SchemaBuilder => {
    this.definition.defaultTimezone = timezone;
    return this;
  };

  /** Set default data source. */
  defaultDataSource = (dataSource: string): SchemaBuilder => {
    this.definition.defaultDataSource = dataSource;
    return this;
  };

  /** Add a table definition. */
  addTable = (builder: TableBuilder | TableDefinition): SchemaBuilder => {
    const table = 'build' in builder ? builder.build() : builder;
    this.tablesMap[table.name] = table;
    return this;
  };

  /** Create and add an inline table. */
  table = (
    name: string,
    sql: string,
    configure: (builder: TableBuilder) => void,
  ): SchemaBuilder => {
    const tableBuilder = new TableBuilder(name, sql);
    configure(tableBuilder);
    this.tablesMap[name] = tableBuilder.build();
    return this;
  };

  /** Attach metadata. */
  meta = (meta: Record<string, unknown>): SchemaBuilder => {
    this.definition.meta = meta;
    return this;
  };

  /** Build schema definition. */
  build = (): SchemaDefinition => {
    if (!this.definition.name || !this.definition.version) {
      throw new Error('Schema definition requires both name and version');
    }

    return {
      name: this.definition.name,
      version: this.definition.version,
      tables: { ...this.tablesMap },
      defaultTimezone: this.definition.defaultTimezone,
      defaultDataSource: this.definition.defaultDataSource,
      meta: this.definition.meta,
    };
  };
}

// =============================================================================
// FACTORY FUNCTIONS
// =============================================================================

/** Create a measure builder. */
export const measure = (aggregation: Aggregation, sql: string): MeasureBuilder =>
  new MeasureBuilder(aggregation, sql);

/** Create a dimension builder. */
export const dimension = (type: DimensionType, sql: string): DimensionBuilder =>
  new DimensionBuilder(type, sql);

/** Create a time dimension builder. */
export const timeDimension = (sql: string): TimeDimensionBuilder => new TimeDimensionBuilder(sql);

/** Create a table builder. */
export const table = (name: string, sql: string): TableBuilder => new TableBuilder(name, sql);

/** Create a schema builder. */
export const schema = (name: string, version?: string): SchemaBuilder =>
  new SchemaBuilder(name, version);

// =============================================================================
// SHORTHAND MEASURE CREATORS
// =============================================================================

const createMeasureFactory =
  (aggregation: Aggregation) =>
  (column: string, title?: string): MeasureDefinition => {
    const builder = new MeasureBuilder(aggregation, column);
    if (title) builder.title(title);
    return builder.build();
  };

/** Create count measure definition. */
export const count = (title?: string): MeasureDefinition => {
  const builder = new MeasureBuilder(AGGREGATIONS.COUNT, '*');
  if (title) builder.title(title);
  return builder.build();
};

/** Create count distinct measure definition. */
export const countDistinct = createMeasureFactory(AGGREGATIONS.COUNT_DISTINCT);

/** Create sum measure definition. */
export const sum = createMeasureFactory(AGGREGATIONS.SUM);

/** Create average measure definition. */
export const avg = createMeasureFactory(AGGREGATIONS.AVG);

/** Create min measure definition. */
export const min = createMeasureFactory(AGGREGATIONS.MIN);

/** Create max measure definition. */
export const max = createMeasureFactory(AGGREGATIONS.MAX);
