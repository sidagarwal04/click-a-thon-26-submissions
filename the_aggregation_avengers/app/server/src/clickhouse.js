// ClickHouse access layer.
//
// Every query is built here from a whitelisted set of shapes -- the HTTP
// handlers pass filters, never SQL. Credentials stay server-side and are never
// sent to the browser.
//
// Two invariants this file exists to protect:
//
//   1. Dimension values are bound as parameters, not interpolated. ClickHouse's
//      {name:Type} parameter syntax is passed via param_* query-string keys, so
//      a value can never be parsed as SQL regardless of what the browser sends.
//
//   2. Peak is computed as max() over the FILTERED per-minute series, never
//      read from a stored per-slice aggregate. max() does not decompose across
//      a filter predicate: Android may peak at 10:05 and Hindi at 10:41 while
//      "Android AND Hindi" peaks at a third minute entirely.

import { readFileSync } from "node:fs";
import { annotateQuery, span } from "./telemetry.js";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));

/** Load .env.local from the repo root -- the same file scripts/ch uses. */
function loadEnv() {
  const env = { ...process.env };
  try {
    const text = readFileSync(resolve(here, "../../../.env.local"), "utf8");
    for (const line of text.split("\n")) {
      const m = line.match(/^([A-Z_]+)=(.*)$/);
      if (m) env[m[1]] ??= m[2];
    }
  } catch {
    /* fall through to process.env */
  }
  if (!env.CH_HOST) throw new Error("CH_HOST not set (expected .env.local at repo root)");
  return env;
}

const ENV = loadEnv();
const AUTH = "Basic " + Buffer.from(`${ENV.CH_USER}:${ENV.CH_PASS}`).toString("base64");

/**
 * Run a query. `params` become ClickHouse query parameters, so values are
 * bound rather than interpolated.
 * Returns { rows, stats } -- stats carries the read_rows / read_bytes that the
 * rubric cares about, surfaced from the X-ClickHouse-Summary response header.
 */
export async function query(sql, params = {}) {
  // The span is what makes the trace CROSS-SYSTEM: it nests inside the HTTP
  // span the auto-instrumentation opens, so one trace shows browser wait, API
  // overhead and ClickHouse time as separate bars. system.query_log only ever
  // sees the innermost one, which is why it cannot answer "where did the time
  // actually go".
  return span("clickhouse.query", { "db.operation": "SELECT" }, async (s) => {
    const qs = new URLSearchParams({ default_format: "JSON" });
    for (const [k, v] of Object.entries(params)) qs.set(`param_${k}`, String(v));

    const started = performance.now();
    const res = await fetch(`${ENV.CH_HOST}/?${qs}`, {
      method: "POST",
      headers: { Authorization: AUTH, "Content-Type": "text/plain" },
      body: sql,
    });
    const body = await res.text();
    if (!res.ok) throw new Error(`ClickHouse ${res.status}: ${body.slice(0, 500)}`);

    const summary = JSON.parse(res.headers.get("x-clickhouse-summary") ?? "{}");
    const parsed = JSON.parse(body);
    const stats = {
      ms: Math.round(performance.now() - started),
      // Server-side truth, not our wall clock: what the query actually touched.
      readRows: Number(summary.read_rows ?? 0),
      readBytes: Number(summary.read_bytes ?? 0),
      chElapsedMs: Math.round((parsed.statistics?.elapsed ?? 0) * 1000),
    };
    annotateQuery(s, { sql, stats });
    return { rows: parsed.data ?? [], stats };
  });
}

// ---------------------------------------------------------------------------
// Filters
// ---------------------------------------------------------------------------

/** Dimensions a caller may filter on. Anything else is ignored, not rejected. */
const FILTERABLE = ["platform", "video_type", "category", "audio_language",
                    "subtitle_language", "app_version", "player_version", "country",
                    // NEW on the unseen dataset. Per-EVENT, not per-session --
                    // the player re-negotiates resolution mid-stream -- so it
                    // behaves like audio_language: one session can span several
                    // values in a minute, which is precisely why gold counts
                    // distinct sessions rather than summing.
                    "video_resolution"];

/**
 * Which gold table can answer this request.
 *
 * `gold_ccu_total` holds one row per minute; `gold_ccu_minute` holds one per
 * minute x dimension combination -- ~27 of them on the provided data, and more
 * once video_resolution lands. When no dimension is being filtered the two
 * return identical numbers (asserted by 40_gold_total.sql), so the smaller
 * table is simply the same answer for less work.
 *
 * Deliberately conservative: ANY dimension predicate falls back to the
 * dimensional table. A wrong route here would return a plausible number for the
 * wrong slice, which is the worst kind of bug -- silent and believable.
 */
function goldTable(filters = {}) {
  const dims = [...FILTERABLE, "content_id"];
  const filtered = dims.some((d) => {
    const v = filters[d];
    return v !== undefined && v !== null && v !== "" && v !== "all";
  });
  return filtered ? "gold_ccu_minute" : "gold_ccu_total";
}

/**
 * Build a WHERE clause from a filter object.
 * `content_id` is handled separately because it is numeric.
 * Returns { where, params } with every value bound as a parameter.
 */
function buildWhere({ from, to, ...filters } = {}) {
  const clauses = [];
  const params = {};

  if (from) {
    clauses.push("minute >= {from:DateTime}");
    params.from = from;
  }
  if (to) {
    clauses.push("minute < {to:DateTime}");
    params.to = to;
  }
  for (const dim of FILTERABLE) {
    const v = filters[dim];
    if (v !== undefined && v !== null && v !== "" && v !== "all") {
      clauses.push(`${dim} = {${dim}:String}`);
      params[dim] = v;
    }
  }
  if (filters.content_id !== undefined && filters.content_id !== "" && filters.content_id !== "all") {
    clauses.push("content_id = {content_id:Int64}");
    params.content_id = filters.content_id;
  }
  return { where: clauses.length ? `WHERE ${clauses.join(" AND ")}` : "", params };
}

// ---------------------------------------------------------------------------
// Query shapes
// ---------------------------------------------------------------------------

/** Minute-grain concurrency series. Everything else derives from this. */
export async function series(filters, withUsers = false) {
  const { where, params } = buildWhere(filters);

  // The chart has the same unbounded-range problem as the rollup, and worse
  // consequences: one <path> per minute means a year of data is ~525,000 points
  // in a single SVG. The browser does not error, it just stops responding.
  //
  // Above the threshold, points are bucketed and each bucket keeps its MAXIMUM
  // minute. That is deliberate rather than an average: max preserves the peak
  // exactly, which is the number this dashboard is about. What it costs is the
  // troughs -- the drawn curve becomes an upper envelope, so it reads slightly
  // busier than reality between peaks. The headline figures are unaffected
  // because the tiles come from /summary, which is always minute-exact.
  //
  // The threshold is on the range's SPAN, not on rows returned -- the row count
  // is only knowable by running the query, which is the thing being guarded
  // against. Gold is sparse (3,856 populated minutes across a 17,026-minute
  // span), so the estimate overshoots and "Full range" DOES downsample today,
  // to 3-minute grain. That is the safe direction to be wrong in, and the peak
  // still reads 2,882 -- but it means the full-range curve is an envelope, and
  // the UI says so rather than leaving it to be discovered.
  const span = await spanSeconds(filters);
  const estimatedPoints = span / 60;
  if (estimatedPoints > MAX_SERIES_POINTS) {
    const bucket = Math.ceil(span / MAX_SERIES_POINTS / 60) * 60;
    const res = await query(
      `SELECT toStartOfInterval(minute, INTERVAL ${bucket} SECOND) AS minute,
              max(ccu) AS ccu, max(user_ccu) AS user_ccu
       FROM (SELECT minute,
                    uniqExactMerge(sessions) AS ccu,
                    ${withUsers ? "uniqExactMerge(users)" : "0"} AS user_ccu
             FROM ${goldTable(filters)} ${where} GROUP BY minute)
       GROUP BY minute ORDER BY minute`,
      params,
    );
    return { ...res, meta: { bucketSeconds: bucket, bucketLabel: `${bucket / 60} min`, downsampled: true } };
  }

  return query(
    // NOT toString(minute) AS minute: the alias would shadow the DateTime
    // column, so the WHERE clause would compare String against DateTime and
    // fail with NO_COMMON_TYPE. ClickHouse already renders DateTime as
    // "YYYY-MM-DD HH:MM:SS" in JSON output, so no cast is needed.
    // The `users` state is only read when the caller asks for it. Reading both
    // states unconditionally DOUBLED every series query -- 37.54 MiB against
    // 19.05 MiB, measured -- to populate an overlay the dashboard hides by
    // default behind "Compare people vs sessions". Columnar storage means the
    // column you do not select is a column you do not pay for; selecting it
    // "just in case" gives that back.
    `SELECT minute,
            uniqExactMerge(sessions) AS ccu,
            ${withUsers ? "uniqExactMerge(users)" : "0"} AS user_ccu
     FROM ${goldTable(filters)} ${where}
     GROUP BY minute ORDER BY minute`,
    params,
  );
}

/**
 * Peak / average / total for the filtered range.
 * Computed over the same series the chart draws -- one source of truth, and
 * structurally incapable of returning a peak that disagrees with the plot.
 */
export function summary(filters) {
  const { where, params } = buildWhere(filters);
  return query(
    `SELECT max(ccu)                      AS peak_ccu,
            toString(argMax(minute, ccu))   AS peak_minute,
            round(avg(ccu), 2)              AS avg_ccu,
            sum(ccu)                        AS watch_minutes,
            count()                         AS minutes_covered,
            max(user_ccu)                   AS peak_user_ccu
     FROM (SELECT minute, uniqExactMerge(sessions) AS ccu,
                  uniqExactMerge(users) AS user_ccu
           FROM ${goldTable(filters)} ${where} GROUP BY minute)`,
    params,
  );
}

/** Hour-grain rollup: peak is the MAX of the minutes inside each hour. */
/**
 * Bucket grains the rollup may choose from, coarsest last.
 *
 * The panel's job is to show the SHAPE of a period. That means a bounded number
 * of bars, always -- not "one row per hour" -- because an hour is only the right
 * bucket for a range measured in days. Over a year, hourly is 8,760 rows: a
 * response nobody reads, a DOM nobody can scroll, and a page that dies long
 * before the data does.
 *
 * PAGINATION WOULD BE THE WRONG FIX. Nobody pages through time buckets to see a
 * shape; they narrow the range -- which the time picker and drag-to-zoom already
 * do. Paging would also make "peak" mean "peak on this page", which is exactly
 * the non-additivity trap the serving layer exists to avoid.
 */
const GRAINS = [
  { approx: 60, unit: "Second", n: 60, label: "minute" },
  { approx: 300, unit: "Second", n: 300, label: "5 minutes" },
  { approx: 900, unit: "Second", n: 900, label: "15 minutes" },
  { approx: 1800, unit: "Second", n: 1800, label: "30 minutes" },
  { approx: 3600, unit: "Second", n: 3600, label: "hour" },
  { approx: 10800, unit: "Second", n: 10800, label: "3 hours" },
  { approx: 21600, unit: "Second", n: 21600, label: "6 hours" },
  { approx: 43200, unit: "Second", n: 43200, label: "12 hours" },
  { approx: 86400, unit: "Day", n: 1, label: "day" },
  { approx: 172800, unit: "Day", n: 2, label: "2 days" },
  { approx: 259200, unit: "Day", n: 3, label: "3 days" },
  { approx: 604800, unit: "Week", n: 1, label: "week" },
  { approx: 2629800, unit: "Month", n: 1, label: "month" },
  { approx: 7889400, unit: "Quarter", n: 1, label: "quarter" },
  { approx: 31557600, unit: "Year", n: 1, label: "year" },
];

// TWO THINGS THIS LADDER HAS TO GET RIGHT.
//
// DENSE, not just long. Each rung is the first grain that fits, so a gap
// between rungs is resolution thrown away: with `day` followed straight by
// `week`, a one-month range (30 buckets, barely over target) fell all the way
// to 5 bars. The 12h/2d/3d rungs catch those overshoots.
//
// LONG ENOUGH TO REACH THE TOP. Stopping at `week` meant a year had nowhere
// coarser to go and returned 53 bars -- a list you have to scroll, and bars you
// cannot compare because you cannot see them at once. Bounding the panel height
// fixed the page layout but not the reading problem. month/quarter/year are the
// actual fix: a year is now 12 bars, five years 20, a decade 10.
//
// Calendar units are NOT expressible in seconds -- months differ in length, and
// a fixed 2,629,800-second bucket drifts off the calendar until a bar labelled
// "Mar" no longer starts in March. So `approx` is used ONLY to choose the rung;
// the SQL always uses the real calendar unit via toIntervalMonth/Quarter/Year.

/**
 * Aim for a readable number of bars; the grain is chosen to land near this.
 *
 * 16, not 24. At 24 the panel kept landing on ~25 bars -- 6 hours became 25
 * fifteen-minute rows, a day became 25 hourly ones -- which scrolls at any
 * sensible card height, and bars you scroll between are bars you cannot
 * compare. That is the whole job of this panel. 16 keeps every range inside the
 * card: a day becomes 9 three-hour bars rather than 25 hourly ones, which is
 * less resolution but more actually read. The minute-grain detail is one panel
 * up in the chart, and drag-to-zoom is there to go find it.
 */
const TARGET_BUCKETS = 16;
/** Hard backstop. Reached only if the span outruns the coarsest grain. */
const MAX_BUCKETS = 200;

/**
 * Above this many minutes in range, the chart series is downsampled.
 *
 * 2,000, not 6,000. The chart is about 1,400 CSS pixels wide, so 6,000 points
 * put four of them behind every pixel -- detail that cannot be seen, paid for
 * in bytes and render time. It also produced absurd grains: a seven-day range
 * came back in TWO-MINUTE buckets, 5,543 points, to draw a week.
 *
 * At 2,000 a week resolves to ~6-minute buckets and a day stays at minute
 * grain. Peak is unaffected either way -- buckets keep their maximum, and the
 * tiles come from /summary, which is always minute-exact.
 */
const MAX_SERIES_POINTS = 2000;

/** Coarsest grain that keeps the bar count at or under the target. */
function pickGrain(spanSeconds) {
  // The tolerance is not fudge. `to` is exclusive, so every range carries one
  // extra minute -- which makes a one-day range 1,441 minutes, or 24.02 hourly
  // buckets. Compared strictly against 24 that tips over the threshold and
  // drops a whole rung: a day rendered as 9 three-hour bars instead of the 24
  // hourly ones anyone asking for "1d" expects. Two buckets of slack absorbs
  // the boundary artifact without letting a genuinely larger range through.
  return (
    GRAINS.find((g) => Math.ceil(spanSeconds / g.approx) <= TARGET_BUCKETS + 2) ??
    GRAINS[GRAINS.length - 1]
  );
}

/** ClickHouse interval expression for a grain, e.g. toIntervalMonth(1). */
const interval = (g) => `toInterval${g.unit}(${g.n})`;

/**
 * The span a request covers, in seconds.
 *
 * When from/to are given this is free. When they are not, the request means
 * "everything", and the extent has to come from the data -- one extra query,
 * but it reads only the primary key and is far cheaper than returning a
 * year of hourly rows.
 */
async function extent({ from, to }) {
  if (from && to) {
    return { from, to, span: Math.max(60, (Date.parse(`${to}Z`) - Date.parse(`${from}Z`)) / 1000) };
  }
  const { rows } = await query(
    `SELECT toString(min(minute)) AS lo, toString(max(minute)) AS hi,
            toUnixTimestamp(max(minute)) - toUnixTimestamp(min(minute)) AS span
     FROM gold_ccu_minute`,
  );
  const r = rows[0] ?? {};
  return { from: from ?? r.lo, to: to ?? r.hi, span: Math.max(60, Number(r.span ?? 60)) };
}

const spanSeconds = async (f) => (await extent(f)).span;

/**
 * Peak and average per bucket, at a grain chosen to fit the range.
 *
 * Peak is `max()` over the MINUTE series inside each bucket -- never an average
 * of averages, and never a stored per-bucket aggregate. Coarsening the display
 * grain must not coarsen the answer: the peak of a day is still the busiest
 * single minute in it.
 */
export async function rollup(filters) {
  const bounds = await extent(filters);
  const grain = pickGrain(bounds.span);
  const { where, params } = buildWhere(filters);

  // WITH FILL, and it is not cosmetic.
  //
  // Without it a bucket containing no data is not returned at all -- so a range
  // covering 14-26 Jul came back as SEVEN rows, with 15-20 Jul missing and the
  // remaining bars rendered adjacent. The panel showed a week-long hole as if it
  // were continuous time, and the bar count silently depended on how sparse the
  // range happened to be (3 days -> 25 bars, 12 days -> 7). Quiet days are data:
  // a day with zero concurrency has to be a zero bar, not an absent one.
  const res = await query(
    `SELECT toString(bucket_ts) AS bucket, peak_ccu, avg_ccu
     FROM (
       SELECT toStartOfInterval(minute, ${interval(grain)}) AS bucket_ts,
              max(ccu) AS peak_ccu, round(avg(ccu), 2) AS avg_ccu
       FROM (SELECT minute, uniqExactMerge(sessions) AS ccu
             FROM ${goldTable(filters)} ${where} GROUP BY minute)
       GROUP BY bucket_ts
       ORDER BY bucket_ts
       WITH FILL
         FROM toStartOfInterval({fill_from:DateTime}, ${interval(grain)})
         TO   toStartOfInterval({fill_to:DateTime},   ${interval(grain)}) + ${interval(grain)}
         STEP ${interval(grain)}
     )
     ORDER BY bucket_ts
     LIMIT ${MAX_BUCKETS + 1}`,
    // Named apart from `from`/`to` so they cannot collide with the filter
    // params buildWhere already bound -- and aliased bucket_ts rather than
    // bucket, because an alias that shadows the column it is computed from is
    // how two earlier queries in this file broke.
    { ...params, fill_from: bounds.from, fill_to: bounds.to },
  );

  // A truncated result is REPORTED, not silently trimmed. A chart that quietly
  // drops its tail reads as "this is all the data", which is a lie the user
  // cannot see.
  const truncated = res.rows.length > MAX_BUCKETS;
  return {
    rows: truncated ? res.rows.slice(0, MAX_BUCKETS) : res.rows,
    stats: res.stats,
    meta: { bucketSeconds: grain.approx, bucketLabel: grain.label, truncated },
  };
}

/** @deprecated kept so /api/hourly does not 404 for anything still calling it. */
export const hourly = rollup;

/** Breakdown by one dimension: each slice's own peak, ranked. */
export function breakdown(dimension, filters) {
  if (![...FILTERABLE, "content_id", "title"].includes(dimension)) {
    throw new Error(`not a filterable dimension: ${dimension}`);
  }
  const { where, params } = buildWhere(filters);
  return query(
    `SELECT toString(${dimension}) AS name, max(ccu) AS peak_ccu, sum(ccu) AS watch_minutes
     FROM (SELECT ${dimension}, minute, uniqExactMerge(sessions) AS ccu
           FROM gold_ccu_minute ${where} GROUP BY ${dimension}, minute)
     GROUP BY name ORDER BY peak_ccu DESC LIMIT 20`,
    params,
  );
}

/**
 * Search titles and show names, for the content picker.
 *
 * A dropdown cannot carry 33,326 titles -- the browser would be shipped the
 * whole catalogue to filter locally. This searches server-side and returns a
 * short ranked list, so the client holds only what it is showing.
 *
 * Ranked by how much was actually WATCHED, not alphabetically: when a term
 * matches forty titles, the one people were watching is almost always the one
 * being looked for. `title` and `show_name` are both searched because a live
 * event is usually a show with many episode-level content_ids.
 */
export function searchContent(term, limit = 20) {
  return query(
    `SELECT toString(c.content_id) AS content_id,
            c.title                AS title,
            c.show_name            AS show_name,
            g.watch_minutes        AS watch_minutes
     FROM silver_content AS c
     LEFT JOIN (
         SELECT content_id, sum(ccu) AS watch_minutes
         FROM (SELECT content_id, minute, uniqExactMerge(sessions) AS ccu
               FROM gold_ccu_minute GROUP BY content_id, minute)
         GROUP BY content_id
     ) AS g ON g.content_id = c.content_id
     WHERE positionCaseInsensitive(c.title, {term:String}) > 0
        OR positionCaseInsensitive(c.show_name, {term:String}) > 0
     ORDER BY watch_minutes DESC, title ASC
     LIMIT ${Number(limit) || 20}`,
    { term: String(term ?? "") },
  );
}

/**
 * Concurrency for one title, or for every title under one show_name.
 *
 * `show_name` is not a gold column -- it lives in the dictionary, because
 * making it a gold dimension would multiply the row count of a table already
 * keyed by ten dimensions. So a show resolves to its content_ids first and the
 * filter is an IN over those, which the proj_content_first projection serves.
 */
export function contentSeries(filters, { contentId, showName } = {}) {
  const { where, params } = buildWhere(filters);
  const clauses = [where.replace(/^WHERE /, "")].filter(Boolean);

  if (showName) {
    clauses.push("content_id IN (SELECT content_id FROM silver_content WHERE show_name = {show:String})");
    params.show = showName;
  } else if (contentId) {
    clauses.push("content_id = {cid:Int64}");
    params.cid = contentId;
  }

  return query(
    `SELECT minute, uniqExactMerge(sessions) AS ccu, uniqExactMerge(users) AS user_ccu
     FROM gold_ccu_minute
     ${clauses.length ? `WHERE ${clauses.join(" AND ")}` : ""}
     GROUP BY minute ORDER BY minute`,
    params,
  );
}

/** Distinct values per dimension, to populate the filter controls. */
export function facets() {
  return query(
    `SELECT
        arraySort(groupUniqArray(platform))       AS platforms,
        arraySort(groupUniqArray(video_type))     AS video_types,
        arraySort(groupUniqArray(audio_language))    AS audio_languages,
        arraySort(groupUniqArray(subtitle_language)) AS subtitle_languages,
        arraySort(groupUniqArray(video_resolution))  AS video_resolutions,
        arraySort(groupUniqArray(app_version))       AS app_versions,
        arraySort(groupUniqArray(player_version))    AS player_versions,
        arraySort(groupUniqArray(country))           AS countries,
        -- THE RANGE THE PICKER OFFERS, not the absolute extremes.
        --
        -- 358 sessions carry skewed client clocks, scattering ~1,225 events
        -- across 189 days from 2023 to 2026-08-03. Those are single-session
        -- artifacts, but min()/max() are order statistics -- one bad row moves
        -- them completely. The damage was not cosmetic: every preset counts
        -- back from max_minute, so "last 3 hours" landed on 2026-08-03, which
        -- holds 9 minutes at a peak of ONE, and the chart came back empty.
        -- "Full range" spanned 1,174 days and drew as a flat line with a spike.
        --
        -- Bounded to minutes carrying at least 10 concurrent sessions. Ten is
        -- a judgement call, and a low one: it is far below any real traffic
        -- here (the busy minutes run to 22,498) and far above the 1-2 sessions
        -- a clock-skew artifact produces, so there is a wide margin either
        -- side. It also anchors the presets to the last minute anyone was
        -- actually watching rather than to the last row in the table -- the
        -- difference between "last 3 hours" showing the surge and showing
        -- twelve hours of empty overnight.
        --
        -- Nothing is hidden. Those rows stay in gold, and an explicitly typed
        -- date still queries them. This decides only what the presets and the
        -- calendar bounds mean.
        (SELECT toString(min(minute)) FROM (
            SELECT minute, uniqExactMerge(sessions) AS ccu
            FROM gold_ccu_total GROUP BY minute
         ) WHERE ccu >= 10)                       AS min_minute,
        (SELECT toString(max(minute)) FROM (
            SELECT minute, uniqExactMerge(sessions) AS ccu
            FROM gold_ccu_total GROUP BY minute
         ) WHERE ccu >= 10)                       AS max_minute,
        -- The TRUE extent, separate from the range above.
        --
        -- These two serve different jobs and conflating them was a bug: the
        -- traffic-bounded range is right for what the PRESETS mean, but wrong
        -- as the calendar's min/max, because it disables every other month and
        -- year outright. The picker must be able to reach every row that
        -- exists -- bounding what it OFFERS is a default, bounding what it
        -- ALLOWS is a cage.
        toString(min(minute))                     AS data_min,
        toString(max(minute))                     AS data_max
     FROM gold_ccu_minute`,
  );
}

/** Pipeline health. Powers the freshness tile and the agent's "did we break?" check. */
export function health() {
  return query(
    `SELECT
        (SELECT count() FROM gold_ccu_minute)                          AS gold_rows,
        (SELECT count() FROM silver_events)                            AS silver_rows,
        (SELECT countIf(is_duplicate = 1) FROM silver_events)          AS flagged_duplicates,
        -- Same bound as the facets range: the header said "data through 3 Aug"
        -- when the last real viewing was 31 Jul, because a handful of
        -- clock-skewed rows sit past the end.
        (SELECT toString(max(minute)) FROM (
            SELECT minute, uniqExactMerge(sessions) AS ccu
            FROM gold_ccu_total GROUP BY minute) WHERE ccu >= 10)     AS latest_minute,
        (SELECT count() FROM clusterAllReplicas(default, system.mutations)
           WHERE NOT is_done)                                          AS pending_mutations`,
  );
}
