import { queryJson } from "../clickhouse.js";

/** Canonical reportable incidents are materialized by ClickHouse's
 * refreshable mv_incidents view. Both this service and the web frontend read
 * the same table so the qualification/grouping policy cannot drift between
 * them. */
export interface IncidentSpan {
  metric: string;
  start_time: string;
  end_time: string;
  span_hours: number;
  flagged_hours: number;
  methods: string[];
  max_abs_z: number;
}

export async function computeIncidentSpans(): Promise<IncidentSpan[]> {
  return queryJson<IncidentSpan>(`
    SELECT metric, start_time, end_time, span_hours, flagged_hours, methods, max_abs_z
    FROM inmobi.incidents
    ORDER BY span_hours DESC, metric, start_time
  `);
}
