/**
 * Query Engine - Core Engine Components
 *
 * This module provides the core orchestration components:
 * - TableExtractor: Extract table names from query members
 * - DecisionEngine: Route queries to API or DuckDB path
 * - FilterConverter: Convert Query filters to data-layer hook args
 *
 * NOTE: Execution is delegated to foundation-data-layer hooks.
 * This module does NOT directly execute queries.
 *
 * @module engine
 */

// =============================================================================
// Table Extractor
// =============================================================================

export {
  TableExtractor,
  createTableExtractor,
  getTableExtractor,
  resetTableExtractor,
  extractTables,
  getPrimaryTable,
  type TableExtractionResult,
} from './table-extractor';

// =============================================================================
// Decision Engine
// =============================================================================

export {
  DecisionEngine,
  createDecisionEngine,
  getDecisionEngine,
  resetDecisionEngine,
  hasDecisionEngineInstance,
  DEFAULT_DECISION_RULES,
  type DecisionEngineConfig,
} from './decision-engine';

// =============================================================================
// Filter Converter
// =============================================================================

export {
  convertFiltersToArgs,
  hasComplexFilters,
  countConvertibleFilters,
  type ConvertedArgs,
} from './filter-converter';
