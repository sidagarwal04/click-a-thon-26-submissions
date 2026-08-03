/**
 * Schema Module for Foundation Query Engine
 *
 * Provides schema registry, builders, and validators.
 *
 * @module schema
 */

// =============================================================================
// Registry
// =============================================================================

export {
  // Class
  SchemaRegistry,
  // Types
  MEMBER_TYPES,
  SCHEMA_ELEMENT_TYPES,
  type MemberType,
  type MemberResolution,
  type SchemaValidationStatus,
  // Errors
  SchemaNotFoundError,
  SchemaValidationError,
  // Factory
  createSchemaRegistry,
} from './registry';

// =============================================================================
// Builders
// =============================================================================

export {
  // Classes
  MeasureBuilder,
  DimensionBuilder,
  TimeDimensionBuilder,
  TableBuilder,
  SchemaBuilder,
  // Factory functions
  measure,
  dimension,
  timeDimension,
  table,
  schema,
  // Shorthand creators
  count,
  countDistinct,
  sum,
  avg,
  min,
  max,
} from './builders';

// =============================================================================
// Validator
// =============================================================================

export {
  // Types
  type ValidationError,
  type DetailedValidationResult,
  // Validators
  validateSchema,
  validateTableDefinition,
  validateQuery,
  // Helpers
  isValidQuery,
  isValidSchema,
  formatValidationErrors,
} from './validator';
