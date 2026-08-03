/**
 * Schema Validator for Foundation Query Engine
 *
 * Provides validation for schema definitions and query specifications.
 *
 * @module schema/validator
 */

import { mapFilterExpression } from '../internal/filter-recursion';
import type { FilterExpression } from '../types/filter';
import type { MeasureSpec } from '../types/measure';
import type { Query } from '../types/query';
import type { SchemaDefinition, TableDefinition } from '../types/schema-definition';
import type { TimeDimensionSpec } from '../types/time';
import type { SchemaRegistry } from './registry';

// =============================================================================
// VALIDATION ERROR TYPES
// =============================================================================

/**
 * Validation error with context.
 */
export interface ValidationError {
  /** Error path (e.g., "query.filters[0].member") */
  readonly path: string;
  /** Error message */
  readonly message: string;
  /** Suggested fix */
  readonly suggestion?: string;
}

/**
 * Detailed validation result.
 */
export interface DetailedValidationResult {
  /** Whether validation passed */
  readonly valid: boolean;
  /** Validation errors */
  readonly errors: ReadonlyArray<ValidationError>;
  /** Validation warnings */
  readonly warnings: ReadonlyArray<ValidationError>;
}

// =============================================================================
// SCHEMA VALIDATOR
// =============================================================================

/**
 * Validate a schema definition.
 */
export const validateSchema = (schema: SchemaDefinition): DetailedValidationResult => {
  const errors: ValidationError[] = [];
  const warnings: ValidationError[] = [];

  if (!schema.name) {
    errors.push({
      path: 'schema.name',
      message: 'Schema name is required',
    });
  }

  if (!schema.version) {
    errors.push({
      path: 'schema.version',
      message: 'Schema version is required',
    });
  }

  if (!schema.tables || Object.keys(schema.tables).length === 0) {
    errors.push({
      path: 'schema.tables',
      message: 'Schema must include at least one table',
    });
    return { valid: false, errors, warnings };
  }

  for (const [tableName, table] of Object.entries(schema.tables)) {
    const tableValidation = validateTableDefinition(table, tableName);
    errors.push(...tableValidation.errors);
    warnings.push(...tableValidation.warnings);
  }

  for (const [tableName, table] of Object.entries(schema.tables)) {
    if (!table.joins) {
      continue;
    }

    for (const [joinName, join] of Object.entries(table.joins)) {
      const targetTable = String(join.table);
      if (!schema.tables[targetTable]) {
        errors.push({
          path: `schema.tables.${tableName}.joins.${joinName}`,
          message: `Join target table '${targetTable}' not found in schema`,
          suggestion: `Add table '${targetTable}' or correct the join target`,
        });
      }
    }
  }

  return {
    valid: errors.length === 0,
    errors,
    warnings,
  };
};

/**
 * Validate a table definition.
 */
export const validateTableDefinition = (
  table: TableDefinition,
  tableName: string,
): DetailedValidationResult => {
  const errors: ValidationError[] = [];
  const warnings: ValidationError[] = [];
  const basePath = `schema.tables.${tableName}`;

  if (!table.name) {
    errors.push({
      path: `${basePath}.name`,
      message: 'Table name is required',
    });
  }

  if (!table.sql) {
    errors.push({
      path: `${basePath}.sql`,
      message: 'Table SQL expression is required',
    });
  }

  if (table.measures) {
    for (const [measureName, measure] of Object.entries(table.measures)) {
      if (!measure.type) {
        errors.push({
          path: `${basePath}.measures.${measureName}.type`,
          message: 'Measure aggregation type is required',
        });
      }

      if (!measure.sql) {
        errors.push({
          path: `${basePath}.measures.${measureName}.sql`,
          message: 'Measure SQL expression is required',
        });
      }
    }
  }

  if (table.dimensions) {
    for (const [dimensionName, dimension] of Object.entries(table.dimensions)) {
      if (!dimension.type) {
        errors.push({
          path: `${basePath}.dimensions.${dimensionName}.type`,
          message: 'Dimension type is required',
        });
      }

      if (!dimension.sql) {
        errors.push({
          path: `${basePath}.dimensions.${dimensionName}.sql`,
          message: 'Dimension SQL expression is required',
        });
      }
    }
  }

  if (!table.measures && !table.dimensions) {
    warnings.push({
      path: basePath,
      message: 'Table has no measures or dimensions',
      suggestion: 'Define at least one measure or dimension to make the table queryable',
    });
  }

  return {
    valid: errors.length === 0,
    errors,
    warnings,
  };
};

// =============================================================================
// QUERY VALIDATOR
// =============================================================================

/**
 * Validate a query against a schema registry.
 */
export const validateQuery = (query: Query, registry: SchemaRegistry): DetailedValidationResult => {
  const errors: ValidationError[] = [];
  const warnings: ValidationError[] = [];

  if (query.measures) {
    for (let index = 0; index < query.measures.length; index++) {
      const measure = query.measures[index];
      const measureValidation = validateMeasureSpec(measure, registry, `query.measures[${index}]`);
      errors.push(...measureValidation.errors);
      warnings.push(...measureValidation.warnings);
    }
  }

  if (query.dimensions) {
    for (let index = 0; index < query.dimensions.length; index++) {
      const dimension = query.dimensions[index];
      const resolved = registry.resolveMember(dimension.member);

      if (!resolved) {
        errors.push({
          path: `query.dimensions[${index}].member`,
          message: `Dimension '${dimension.member}' not found in schema`,
          suggestion: 'Use a valid member reference from the registered schema',
        });
      } else if (resolved.type !== 'dimension') {
        errors.push({
          path: `query.dimensions[${index}].member`,
          message: `'${dimension.member}' resolves to a ${resolved.type}, not a dimension`,
          suggestion: 'Move this member into measures if it is intended for aggregation',
        });
      }
    }
  }

  if (query.timeDimensions) {
    for (let index = 0; index < query.timeDimensions.length; index++) {
      const timeDimension = query.timeDimensions[index];
      const timeDimensionValidation = validateTimeDimension(
        timeDimension,
        registry,
        `query.timeDimensions[${index}]`,
      );
      errors.push(...timeDimensionValidation.errors);
      warnings.push(...timeDimensionValidation.warnings);
    }
  }

  if (query.filters) {
    for (let index = 0; index < query.filters.length; index++) {
      const filter = query.filters[index];
      const filterValidation = validateFilterExpression(
        filter,
        registry,
        `query.filters[${index}]`,
      );
      errors.push(...filterValidation.errors);
      warnings.push(...filterValidation.warnings);
    }
  }

  if (query.orderBy) {
    for (let index = 0; index < query.orderBy.length; index++) {
      const orderSpec = query.orderBy[index];
      const resolved = registry.resolveMember(orderSpec.member);
      if (!resolved) {
        errors.push({
          path: `query.orderBy[${index}].member`,
          message: `Order member '${orderSpec.member}' not found in schema`,
          suggestion: 'Use a valid schema member for ordering',
        });
      }
    }
  }

  if (query.limit !== undefined && query.limit < 0) {
    errors.push({
      path: 'query.limit',
      message: 'Limit must be greater than or equal to 0',
    });
  }

  if (query.offset !== undefined && query.offset < 0) {
    errors.push({
      path: 'query.offset',
      message: 'Offset must be greater than or equal to 0',
    });
  }

  if (query.ungrouped && query.measures && query.measures.length > 0) {
    warnings.push({
      path: 'query.ungrouped',
      message: 'Ungrouped query with measures can produce unexpected semantics',
      suggestion: 'Confirm this query shape is intentional',
    });
  }

  return {
    valid: errors.length === 0,
    errors,
    warnings,
  };
};

const validateMeasureSpec = (
  measure: MeasureSpec,
  registry: SchemaRegistry,
  path: string,
): DetailedValidationResult => {
  const errors: ValidationError[] = [];
  const warnings: ValidationError[] = [];

  if (measure.member !== '*') {
    const resolved = registry.resolveMember(measure.member);
    if (!resolved) {
      errors.push({
        path: `${path}.member`,
        message: `Measure member '${measure.member}' not found in schema`,
        suggestion: 'Use a registered schema member or add it to the schema',
      });
    }
  }

  if (!measure.aggregation) {
    errors.push({
      path: `${path}.aggregation`,
      message: 'Measure aggregation is required',
    });
  }

  return {
    valid: errors.length === 0,
    errors,
    warnings,
  };
};

const validateTimeDimension = (
  timeDimension: TimeDimensionSpec,
  registry: SchemaRegistry,
  path: string,
): DetailedValidationResult => {
  const errors: ValidationError[] = [];
  const warnings: ValidationError[] = [];

  const resolved = registry.resolveMember(timeDimension.dimension);
  if (!resolved) {
    errors.push({
      path: `${path}.dimension`,
      message: `Time dimension '${timeDimension.dimension}' not found in schema`,
      suggestion: 'Use a registered time dimension member',
    });
  } else if (resolved.type !== 'dimension') {
    errors.push({
      path: `${path}.dimension`,
      message: `'${timeDimension.dimension}' resolves to ${resolved.type}, not dimension`,
    });
  } else if (resolved.definition.type !== 'time') {
    warnings.push({
      path: `${path}.dimension`,
      message: `'${timeDimension.dimension}' is not typed as a time dimension`,
      suggestion: 'Use a dimension with type "time" for date bucketing',
    });
  }

  return {
    valid: errors.length === 0,
    errors,
    warnings,
  };
};

const validateFilterExpression = (
  filter: FilterExpression,
  registry: SchemaRegistry,
  path: string,
): DetailedValidationResult => {
  return mapFilterExpression(filter, {
    onCondition: (condition) => {
      const errors: ValidationError[] = [];
      const warnings: ValidationError[] = [];

      const resolved = registry.resolveMember(condition.member);
      if (!resolved) {
        errors.push({
          path: `${path}.member`,
          message: `Filter member '${condition.member}' not found in schema`,
        });
      }

      return {
        valid: errors.length === 0,
        errors,
        warnings,
      };
    },
    onAndGroup: (children) => {
      const errors: ValidationError[] = [];
      const warnings: ValidationError[] = [];
      for (const child of children) {
        errors.push(...child.errors);
        warnings.push(...child.warnings);
      }
      return {
        valid: errors.length === 0,
        errors,
        warnings,
      };
    },
    onOrGroup: (children) => {
      const errors: ValidationError[] = [];
      const warnings: ValidationError[] = [];
      for (const child of children) {
        errors.push(...child.errors);
        warnings.push(...child.warnings);
      }
      return {
        valid: errors.length === 0,
        errors,
        warnings,
      };
    },
  });
};

// =============================================================================
// VALIDATION HELPERS
// =============================================================================

/**
 * Quick query validation helper.
 */
export const isValidQuery = (query: Query, registry: SchemaRegistry): boolean =>
  validateQuery(query, registry).valid;

/**
 * Quick schema validation helper.
 */
export const isValidSchema = (schema: SchemaDefinition): boolean => validateSchema(schema).valid;

/**
 * Format validation result for logs/UI.
 */
export const formatValidationErrors = (result: DetailedValidationResult): string => {
  if (result.valid) {
    return 'Validation passed';
  }

  const lines: string[] = ['Validation failed:'];

  for (const error of result.errors) {
    lines.push(`  - ${error.path}: ${error.message}`);
    if (error.suggestion) {
      lines.push(`    Suggestion: ${error.suggestion}`);
    }
  }

  if (result.warnings.length > 0) {
    lines.push('Warnings:');
    for (const warning of result.warnings) {
      lines.push(`  - ${warning.path}: ${warning.message}`);
      if (warning.suggestion) {
        lines.push(`    Suggestion: ${warning.suggestion}`);
      }
    }
  }

  return lines.join('\n');
};
