/**
 * Time Types for Foundation Query Engine
 *
 * Defines time granularities, date ranges, and time dimension specifications.
 * Uses const objects with derived types pattern.
 *
 * @module types/time
 */

import type { MemberRef } from '@open-zentra/foundation-data-model';

// =============================================================================
// TIME GRANULARITIES - Const object pattern
// =============================================================================

/**
 * Time granularity levels for grouping
 */
export const TIME_GRANULARITIES = {
  /** Per second */
  SECOND: 'second',
  /** Per minute */
  MINUTE: 'minute',
  /** Per hour */
  HOUR: 'hour',
  /** Per day */
  DAY: 'day',
  /** Per week */
  WEEK: 'week',
  /** Per month */
  MONTH: 'month',
  /** Per quarter */
  QUARTER: 'quarter',
  /** Per year */
  YEAR: 'year',
} as const;

/**
 * Time granularity type derived from TIME_GRANULARITIES
 */
export type TimeGranularity = (typeof TIME_GRANULARITIES)[keyof typeof TIME_GRANULARITIES];

// =============================================================================
// TIME UNITS - Const object pattern
// =============================================================================

/**
 * Time units for relative date calculations
 */
export const TIME_UNITS = {
  /** Seconds */
  SECOND: 'second',
  /** Minutes */
  MINUTE: 'minute',
  /** Hours */
  HOUR: 'hour',
  /** Days */
  DAY: 'day',
  /** Weeks */
  WEEK: 'week',
  /** Months */
  MONTH: 'month',
  /** Quarters */
  QUARTER: 'quarter',
  /** Years */
  YEAR: 'year',
} as const;

/**
 * Time unit type derived from TIME_UNITS
 */
export type TimeUnit = (typeof TIME_UNITS)[keyof typeof TIME_UNITS];

// =============================================================================
// PRESET DATE RANGES - Const object pattern
// =============================================================================

/**
 * Pre-defined date range presets
 */
export const PRESET_DATE_RANGES = {
  /** Today only */
  TODAY: 'today',
  /** Yesterday only */
  YESTERDAY: 'yesterday',
  /** Current week (Monday to Sunday) */
  THIS_WEEK: 'this_week',
  /** Previous week */
  LAST_WEEK: 'last_week',
  /** Current month */
  THIS_MONTH: 'this_month',
  /** Previous month */
  LAST_MONTH: 'last_month',
  /** Current quarter */
  THIS_QUARTER: 'this_quarter',
  /** Previous quarter */
  LAST_QUARTER: 'last_quarter',
  /** Current year */
  THIS_YEAR: 'this_year',
  /** Previous year */
  LAST_YEAR: 'last_year',
  /** Last 7 days rolling */
  LAST_7_DAYS: 'last_7_days',
  /** Last 14 days rolling */
  LAST_14_DAYS: 'last_14_days',
  /** Last 30 days rolling */
  LAST_30_DAYS: 'last_30_days',
  /** Last 60 days rolling */
  LAST_60_DAYS: 'last_60_days',
  /** Last 90 days rolling */
  LAST_90_DAYS: 'last_90_days',
  /** Last 365 days rolling */
  LAST_365_DAYS: 'last_365_days',
  /** All available data */
  ALL_TIME: 'all_time',
} as const;

/**
 * Preset date range type derived from PRESET_DATE_RANGES
 */
export type PresetDateRange = (typeof PRESET_DATE_RANGES)[keyof typeof PRESET_DATE_RANGES];

// =============================================================================
// DATE RANGE STRUCTURES
// =============================================================================

/**
 * Absolute date range with start and end dates
 */
export interface DateRange {
  /** Start date (ISO 8601 format) */
  readonly from: string;
  /** End date (ISO 8601 format) */
  readonly to: string;
}

/**
 * Relative date range based on time units
 */
export interface RelativeDateRange {
  /** Number of units */
  readonly value: number;
  /** Time unit */
  readonly unit: TimeUnit;
  /** Offset from current period (negative for past) */
  readonly offset?: number;
}

/**
 * Date range specification - multiple formats supported
 * Union of actual types (allowed per design guidelines)
 */
export type DateRangeSpec =
  | PresetDateRange
  | DateRange
  | readonly [string, string]
  | RelativeDateRange;

/**
 * Time dimension specification for queries
 */
export interface TimeDimensionSpec {
  /** Time dimension column reference */
  readonly dimension: MemberRef;
  /** Granularity for grouping (optional if only filtering) */
  readonly granularity?: TimeGranularity;
  /** Date range to filter by */
  readonly dateRange?: DateRangeSpec;
  /** Comparison date range for period-over-period analysis */
  readonly compareTo?: DateRangeSpec;
}

// =============================================================================
// TYPE GUARDS
// =============================================================================

/**
 * Check if a value is a preset date range
 */
export const isPresetDateRange = (range: DateRangeSpec): range is PresetDateRange =>
  typeof range === 'string' && Object.values(PRESET_DATE_RANGES).includes(range as PresetDateRange);

/**
 * Check if a value is an absolute date range
 */
export const isDateRange = (range: DateRangeSpec): range is DateRange =>
  typeof range === 'object' && !Array.isArray(range) && 'from' in range && 'to' in range;

/**
 * Check if a value is a date range tuple
 */
export const isDateRangeTuple = (range: DateRangeSpec): range is readonly [string, string] =>
  Array.isArray(range) && range.length === 2 && typeof range[0] === 'string';

/**
 * Check if a value is a relative date range
 */
export const isRelativeDateRange = (range: DateRangeSpec): range is RelativeDateRange =>
  typeof range === 'object' && !Array.isArray(range) && 'value' in range && 'unit' in range;

/**
 * Check if a value is a valid time granularity
 */
export const isTimeGranularity = (value: unknown): value is TimeGranularity =>
  typeof value === 'string' && Object.values(TIME_GRANULARITIES).includes(value as TimeGranularity);

/**
 * Check if a value is a valid time unit
 */
export const isTimeUnit = (value: unknown): value is TimeUnit =>
  typeof value === 'string' && Object.values(TIME_UNITS).includes(value as TimeUnit);

// =============================================================================
// GRANULARITY CONSTANTS
// =============================================================================

/**
 * Milliseconds per granularity unit (approximate for months/years)
 */
export const GRANULARITY_MS: Record<TimeGranularity, number> = {
  [TIME_GRANULARITIES.SECOND]: 1000,
  [TIME_GRANULARITIES.MINUTE]: 60 * 1000,
  [TIME_GRANULARITIES.HOUR]: 60 * 60 * 1000,
  [TIME_GRANULARITIES.DAY]: 24 * 60 * 60 * 1000,
  [TIME_GRANULARITIES.WEEK]: 7 * 24 * 60 * 60 * 1000,
  [TIME_GRANULARITIES.MONTH]: 30 * 24 * 60 * 60 * 1000,
  [TIME_GRANULARITIES.QUARTER]: 91 * 24 * 60 * 60 * 1000,
  [TIME_GRANULARITIES.YEAR]: 365 * 24 * 60 * 60 * 1000,
} as const;

/**
 * Granularity order from finest to coarsest
 */
export const GRANULARITY_ORDER = [
  TIME_GRANULARITIES.SECOND,
  TIME_GRANULARITIES.MINUTE,
  TIME_GRANULARITIES.HOUR,
  TIME_GRANULARITIES.DAY,
  TIME_GRANULARITIES.WEEK,
  TIME_GRANULARITIES.MONTH,
  TIME_GRANULARITIES.QUARTER,
  TIME_GRANULARITIES.YEAR,
] as const;

// =============================================================================
// GRANULARITY HELPERS
// =============================================================================

/**
 * Compare two granularities
 * @returns negative if a < b, 0 if equal, positive if a > b
 */
export const compareGranularities = (a: TimeGranularity, b: TimeGranularity): number => {
  const indexA = GRANULARITY_ORDER.indexOf(a);
  const indexB = GRANULARITY_ORDER.indexOf(b);
  return indexA - indexB;
};

/**
 * Check if granularity a is finer than granularity b
 */
export const isGranularityFiner = (a: TimeGranularity, b: TimeGranularity): boolean =>
  compareGranularities(a, b) < 0;

/**
 * Mapping from TimeGranularity to DuckDB date_trunc unit name.
 * Module-level constant avoids re-creating the record on every call.
 */
const DATE_TRUNC_UNIT_MAP: Readonly<Record<TimeGranularity, string>> = {
  [TIME_GRANULARITIES.SECOND]: 'second',
  [TIME_GRANULARITIES.MINUTE]: 'minute',
  [TIME_GRANULARITIES.HOUR]: 'hour',
  [TIME_GRANULARITIES.DAY]: 'day',
  [TIME_GRANULARITIES.WEEK]: 'week',
  [TIME_GRANULARITIES.MONTH]: 'month',
  [TIME_GRANULARITIES.QUARTER]: 'quarter',
  [TIME_GRANULARITIES.YEAR]: 'year',
};

/**
 * Get the DuckDB date_trunc unit name
 */
export const getDateTruncUnit = (granularity: TimeGranularity): string => {
  return DATE_TRUNC_UNIT_MAP[granularity];
};

/**
 * Calculate the start and end dates for a preset date range
 * @param preset - Preset date range
 * @param referenceDate - Reference date (defaults to now)
 * @returns DateRange with ISO 8601 date strings
 */
export const resolvePresetDateRange = (
  preset: PresetDateRange,
  referenceDate: Date = new Date(),
): DateRange => {
  const today = new Date(referenceDate);
  today.setHours(0, 0, 0, 0);

  const formatDate = (d: Date): string => d.toISOString().split('T')[0];

  switch (preset) {
    case PRESET_DATE_RANGES.TODAY: {
      return { from: formatDate(today), to: formatDate(today) };
    }
    case PRESET_DATE_RANGES.YESTERDAY: {
      const yesterday = new Date(today);
      yesterday.setDate(yesterday.getDate() - 1);
      return { from: formatDate(yesterday), to: formatDate(yesterday) };
    }
    case PRESET_DATE_RANGES.THIS_WEEK: {
      const startOfWeek = new Date(today);
      const day = startOfWeek.getDay();
      const diff = startOfWeek.getDate() - day + (day === 0 ? -6 : 1);
      startOfWeek.setDate(diff);
      const endOfWeek = new Date(startOfWeek);
      endOfWeek.setDate(endOfWeek.getDate() + 6);
      return { from: formatDate(startOfWeek), to: formatDate(endOfWeek) };
    }
    case PRESET_DATE_RANGES.LAST_WEEK: {
      const startOfLastWeek = new Date(today);
      const day = startOfLastWeek.getDay();
      const diff = startOfLastWeek.getDate() - day + (day === 0 ? -6 : 1) - 7;
      startOfLastWeek.setDate(diff);
      const endOfLastWeek = new Date(startOfLastWeek);
      endOfLastWeek.setDate(endOfLastWeek.getDate() + 6);
      return { from: formatDate(startOfLastWeek), to: formatDate(endOfLastWeek) };
    }
    case PRESET_DATE_RANGES.THIS_MONTH: {
      const startOfMonth = new Date(today.getFullYear(), today.getMonth(), 1);
      const endOfMonth = new Date(today.getFullYear(), today.getMonth() + 1, 0);
      return { from: formatDate(startOfMonth), to: formatDate(endOfMonth) };
    }
    case PRESET_DATE_RANGES.LAST_MONTH: {
      const startOfLastMonth = new Date(today.getFullYear(), today.getMonth() - 1, 1);
      const endOfLastMonth = new Date(today.getFullYear(), today.getMonth(), 0);
      return { from: formatDate(startOfLastMonth), to: formatDate(endOfLastMonth) };
    }
    case PRESET_DATE_RANGES.THIS_QUARTER: {
      const quarter = Math.floor(today.getMonth() / 3);
      const startOfQuarter = new Date(today.getFullYear(), quarter * 3, 1);
      const endOfQuarter = new Date(today.getFullYear(), quarter * 3 + 3, 0);
      return { from: formatDate(startOfQuarter), to: formatDate(endOfQuarter) };
    }
    case PRESET_DATE_RANGES.LAST_QUARTER: {
      const quarter = Math.floor(today.getMonth() / 3);
      const startOfLastQuarter = new Date(today.getFullYear(), (quarter - 1) * 3, 1);
      const endOfLastQuarter = new Date(today.getFullYear(), quarter * 3, 0);
      return { from: formatDate(startOfLastQuarter), to: formatDate(endOfLastQuarter) };
    }
    case PRESET_DATE_RANGES.THIS_YEAR: {
      const startOfYear = new Date(today.getFullYear(), 0, 1);
      const endOfYear = new Date(today.getFullYear(), 11, 31);
      return { from: formatDate(startOfYear), to: formatDate(endOfYear) };
    }
    case PRESET_DATE_RANGES.LAST_YEAR: {
      const startOfLastYear = new Date(today.getFullYear() - 1, 0, 1);
      const endOfLastYear = new Date(today.getFullYear() - 1, 11, 31);
      return { from: formatDate(startOfLastYear), to: formatDate(endOfLastYear) };
    }
    case PRESET_DATE_RANGES.LAST_7_DAYS: {
      const startDate = new Date(today);
      startDate.setDate(startDate.getDate() - 6);
      return { from: formatDate(startDate), to: formatDate(today) };
    }
    case PRESET_DATE_RANGES.LAST_14_DAYS: {
      const startDate = new Date(today);
      startDate.setDate(startDate.getDate() - 13);
      return { from: formatDate(startDate), to: formatDate(today) };
    }
    case PRESET_DATE_RANGES.LAST_30_DAYS: {
      const startDate = new Date(today);
      startDate.setDate(startDate.getDate() - 29);
      return { from: formatDate(startDate), to: formatDate(today) };
    }
    case PRESET_DATE_RANGES.LAST_60_DAYS: {
      const startDate = new Date(today);
      startDate.setDate(startDate.getDate() - 59);
      return { from: formatDate(startDate), to: formatDate(today) };
    }
    case PRESET_DATE_RANGES.LAST_90_DAYS: {
      const startDate = new Date(today);
      startDate.setDate(startDate.getDate() - 89);
      return { from: formatDate(startDate), to: formatDate(today) };
    }
    case PRESET_DATE_RANGES.LAST_365_DAYS: {
      const startDate = new Date(today);
      startDate.setDate(startDate.getDate() - 364);
      return { from: formatDate(startDate), to: formatDate(today) };
    }
    case PRESET_DATE_RANGES.ALL_TIME:
    default: {
      return { from: '1970-01-01', to: formatDate(today) };
    }
  }
};
