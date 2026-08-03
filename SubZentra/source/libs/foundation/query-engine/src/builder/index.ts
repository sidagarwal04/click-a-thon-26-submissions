/**
 * Query Builder Module for Foundation Query Engine
 *
 * Provides fluent API for building queries and common presets.
 *
 * @module builder
 */

// =============================================================================
// Query Builder
// =============================================================================

export { QueryBuilder, createQueryBuilder, filterCondition } from './query-builder';

// =============================================================================
// Presets
// =============================================================================

export {
  // Preset types
  type PresetOptions,
  type TimeSeriesPresetOptions,
  // Aggregate presets
  countQuery,
  countByDimension,
  sumByDimension,
  // Time series presets
  timeSeriesCount,
  timeSeriesSum,
  timeSeriesMetrics,
  // Dashboard presets
  kpiQuery,
  comparisonKpiQuery,
  topNQuery,
  // Filtered presets
  filteredCount,
  filteredAggregation,
  // Real-time presets
  realtimeQuery,
  // Utilities
  extendPreset,
} from './presets';
