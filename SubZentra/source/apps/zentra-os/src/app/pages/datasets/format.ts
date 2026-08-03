import type { HarvestPhase } from './types';

/** Row counts read better grouped than as a bare integer. */
export const formatRows = (value: number | null | undefined): string =>
  value == null ? '—' : value.toLocaleString();

export const formatBytes = (value: number | null | undefined): string => {
  if (value == null) return '—';
  if (value < 1024) return `${value} B`;
  const units = ['KiB', 'MiB', 'GiB', 'TiB'];
  let size = value / 1024;
  let unit = 0;
  while (size >= 1024 && unit < units.length - 1) {
    size /= 1024;
    unit += 1;
  }
  return `${size < 10 ? size.toFixed(1) : Math.round(size)} ${units[unit]}`;
};

/**
 * A fraction as a percentage, keeping one decimal only where it carries
 * information — "0.0%" and "0%" say different things about a null column.
 */
export const formatFraction = (value: number | null | undefined): string => {
  if (value == null) return '—';
  const pct = value * 100;
  if (pct === 0) return '0%';
  if (pct < 0.1) return '<0.1%';
  return `${pct < 10 ? pct.toFixed(1) : Math.round(pct)}%`;
};

export const PHASE_LABEL: Record<HarvestPhase, string> = {
  pending: 'Queued',
  connecting: 'Connecting',
  listing_tables: 'Listing tables',
  describing_fields: 'Describing fields',
  profiling: 'Profiling',
  inferring_relations: 'Inferring relations',
  completed: 'Completed',
  failed: 'Failed',
  cancelled: 'Cancelled',
};

/** Coarse failure codes the API is allowed to hand out, said usefully. */
export const HARVEST_FAILURE_HELP: Record<string, string> = {
  unreachable:
    'Nothing answered at that host and port. The service may have been paused or its network closed.',
  authentication_failed:
    'The host answered but rejected the stored credentials — they may have been rotated since this source was registered.',
  database_not_found:
    'The credentials worked, but that database no longer exists on the service.',
};
