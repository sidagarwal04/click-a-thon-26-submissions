/**
 * Every KPI is derived from conc_minute, the minute x dimension serving
 * table. Two rules govern all of it:
 *
 *   1. `sessions` is SimpleAggregateFunction(max, ...), so it must be
 *      collapsed with max() at its own grain before anything else.
 *   2. Concurrency is additive ACROSS dimensions at a fixed minute (a
 *      session has exactly one platform, one country, one content) but
 *      NOT across minutes. So: sum across dims, then max over minutes.
 *      Never the other way round, and never a stored peak.
 */

export const SEGMENT_DIMENSIONS = {
  platform: { column: 'platform', label: 'Platform' },
  country: { column: 'country', label: 'Country' },
  video_type: { column: 'video_type', label: 'Content type' },
  content_id: { column: 'content_id', label: 'Title' },
};

/** Builds the shared WHERE clause. Values go through query parameters. */
export function buildFilter(f = {}) {
  const clauses = ['minute >= {p_from:DateTime}', 'minute < {p_to:DateTime}'];
  const params = { p_from: f.from, p_to: f.to };

  if (f.platform) { clauses.push('platform = {p_platform:String}'); params.p_platform = f.platform; }
  if (f.country) { clauses.push('country = {p_country:String}'); params.p_country = f.country; }
  if (f.video_type) { clauses.push('video_type = {p_video_type:String}'); params.p_video_type = f.video_type; }
  if (f.content_id) { clauses.push('content_id = {p_content_id:UInt32}'); params.p_content_id = Number(f.content_id); }

  return { where: clauses.join('\n    AND '), params };
}

/** Collapses max-semantics rows at their own grain, then filters. */
const BASE = (where) => `
  base AS (
    SELECT minute, platform, country, video_type, content_id,
           max(sessions) AS sessions
    FROM conc_minute
    WHERE ${where}
    GROUP BY minute, platform, country, video_type, content_id
  ),
  per_minute AS (
    SELECT minute, sum(sessions) AS c FROM base GROUP BY minute
  )`;

/**
 * Keeps the chart under ~1500 points on long ranges by bucketing.
 * Buckets take max(), not avg(), so the peak minute survives downsampling
 * intact — averaging would flatten exactly the value the page is about.
 */
export function bucketSeconds(fromISO, toISO, target = 1500) {
  const mins = Math.max(1, (new Date(toISO) - new Date(fromISO)) / 60000);
  return Math.max(60, Math.ceil(mins / target) * 60);
}

export const overviewQueries = (f) => {
  const { where, params } = buildFilter(f);
  const bucket = bucketSeconds(f.from, f.to);
  const p = { ...params, p_bucket: bucket };

  return [
    {
      name: 'summary',
      params: p,
      sql: `
        WITH ${BASE(where)}
        SELECT
          max(c)                                          AS peak_concurrency,
          argMax(minute, c)                               AS peak_minute,
          round(sum(c) / greatest(1, dateDiff('minute', {p_from:DateTime}, {p_to:DateTime})), 2)
                                                          AS avg_concurrency,
          sum(c)                                          AS active_session_minutes,
          count()                                         AS minutes_with_viewing,
          dateDiff('minute', {p_from:DateTime}, {p_to:DateTime}) AS minutes_in_range
        FROM per_minute`,
    },
    {
      name: 'reach',
      params,
      sql: `
        SELECT
          max(u)            AS peak_concurrent_users,
          argMax(minute, u) AS peak_users_minute
        FROM (
          SELECT minute, uniqExactMerge(users) AS u
          FROM conc_minute
          WHERE ${where}
          GROUP BY minute
        )`,
    },
    {
      name: 'timeseries',
      params: p,
      sql: `
        WITH ${BASE(where)}
        SELECT
          toStartOfInterval(minute, INTERVAL {p_bucket:UInt32} SECOND) AS t,
          max(c) AS peak,
          round(avg(c), 2) AS avg
        FROM per_minute
        GROUP BY t ORDER BY t`,
    },
    {
      name: 'hourly',
      params: p,
      sql: `
        WITH ${BASE(where)}
        SELECT
          toStartOfHour(minute) AS hour,
          max(c)                AS peak,
          round(sum(c) / 60, 2) AS avg
        FROM per_minute
        GROUP BY hour ORDER BY hour`,
    },
    {
      name: 'platform_mix',
      params,
      sql: `
        WITH ${BASE(where)},
        per_seg AS (
          SELECT platform AS seg, minute, sum(sessions) AS c
          FROM base GROUP BY seg, minute
        )
        SELECT seg AS label, max(c) AS peak, argMax(minute, c) AS peak_minute, sum(c) AS session_minutes
        FROM per_seg GROUP BY seg ORDER BY peak DESC`,
    },
    {
      name: 'top_content',
      params,
      sql: `
        WITH ${BASE(where)},
        per_seg AS (
          SELECT content_id, minute, sum(sessions) AS c
          FROM base GROUP BY content_id, minute
        )
        SELECT
          content_id,
          joinGet('liv.content_join', 'title', content_id) AS title,
          joinGet('liv.content_join', 'video_type', content_id) AS video_type,
          max(c)            AS peak,
          argMax(minute, c) AS peak_minute,
          sum(c)            AS session_minutes
        FROM per_seg
        GROUP BY content_id
        ORDER BY peak DESC, session_minutes DESC
        LIMIT 12`,
    },
  ];
};

export const segmentQueries = (f, dimKey, topN = 8) => {
  const dim = SEGMENT_DIMENSIONS[dimKey];
  if (!dim) throw new Error(`unknown segment dimension: ${dimKey}`);

  const { where, params } = buildFilter(f);
  const bucket = bucketSeconds(f.from, f.to);
  const col = dim.column; // whitelisted above, never user text
  const label =
    col === 'content_id'
      ? `joinGet('liv.content_join', 'title', content_id)`
      : `toString(${col})`;

  const p = { ...params, p_bucket: bucket, p_topn: topN };

  return [
    {
      name: 'breakdown',
      params: p,
      sql: `
        WITH ${BASE(where)},
        per_seg AS (
          SELECT ${col} AS seg, ${label} AS seg_label, minute, sum(sessions) AS c
          FROM base GROUP BY seg, seg_label, minute
        ),
        totals AS (SELECT sum(c) AS grand FROM per_seg)
        SELECT
          toString(seg)     AS seg,
          any(seg_label)    AS seg_label,
          max(c)            AS peak,
          argMax(minute, c) AS peak_minute,
          round(sum(c) / greatest(1, dateDiff('minute', {p_from:DateTime}, {p_to:DateTime})), 2) AS avg,
          sum(c)            AS session_minutes,
          round(100 * sum(c) / (SELECT grand FROM totals), 2) AS share_pct
        FROM per_seg
        GROUP BY seg
        ORDER BY peak DESC
        LIMIT {p_topn:UInt32}`,
    },
    {
      name: 'series',
      params: p,
      sql: `
        WITH ${BASE(where)},
        per_seg AS (
          SELECT ${col} AS seg, ${label} AS seg_label, minute, sum(sessions) AS c
          FROM base GROUP BY seg, seg_label, minute
        ),
        top AS (
          SELECT seg FROM per_seg GROUP BY seg ORDER BY max(c) DESC LIMIT {p_topn:UInt32}
        )
        SELECT
          toStartOfInterval(minute, INTERVAL {p_bucket:UInt32} SECOND) AS t,
          any(seg_label) AS seg_label,
          max(c) AS peak
        FROM per_seg
        WHERE seg IN (SELECT seg FROM top)
        GROUP BY t, seg
        ORDER BY t`,
    },
    {
      name: 'concentration',
      params: p,
      sql: `
        WITH ${BASE(where)},
        per_seg AS (
          SELECT ${col} AS seg, minute, sum(sessions) AS c FROM base GROUP BY seg, minute
        ),
        by_seg AS (SELECT seg, sum(c) AS sm FROM per_seg GROUP BY seg)
        SELECT
          count()                                        AS segments,
          round(100 * max(sm) / sum(sm), 2)              AS largest_share_pct,
          round(100 * sum(if(sm >= q90, sm, 0)) / sum(sm), 2) AS top_decile_share_pct
        FROM by_seg, (SELECT quantileExact(0.9)(sm) AS q90 FROM by_seg)`,
    },
  ];
};

export const metaQuery = () => [
  {
    name: 'meta',
    params: {},
    sql: `
      SELECT
        min(minute)                     AS min_minute,
        max(minute) + INTERVAL 1 MINUTE AS max_minute,
        groupUniqArray(platform)        AS platforms,
        groupUniqArray(country)         AS countries,
        groupUniqArray(video_type)      AS video_types
      FROM conc_minute`,
  },
];
