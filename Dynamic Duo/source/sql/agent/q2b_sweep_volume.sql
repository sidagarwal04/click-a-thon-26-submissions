-- Q2b · Dimension sweep, volume (requests / fills / impressions counts)
-- Fragments: __DIM__  __VOLUME_EXPR__  __SEG_FILTER__      (README whitelist)
-- Params   : {inc_dates:Array(Date)}  {base_dates:Array(Date)}  {datasets:Array(String)}
-- Expected per segment = per-weekday median of its daily volume, weighted by the
-- incident's weekday mix (baseline rule 1 applied at segment level).
-- Runner: uniform pct_change across segments of every dim -> GLOBAL (q5 confirms);
--         share_of_total_change mirrors segment size on uniform moves - not localization.
WITH per_day AS (
  SELECT __DIM__ AS seg, event_date AS d, toDayOfWeek(event_date) AS dow,
         sum(__VOLUME_EXPR__) AS vol
  FROM rca.ad_events_enriched
  WHERE (event_date IN ({inc_dates:Array(Date)}) OR event_date IN ({base_dates:Array(Date)}))
    AND dataset IN ({datasets:Array(String)})
    AND __SEG_FILTER__
  AND __SCOPE_FILTER__
  GROUP BY seg, d, dow
),
inc_dow AS (
  SELECT dow, count(DISTINCT d) AS n FROM per_day
  WHERE d IN ({inc_dates:Array(Date)}) GROUP BY dow
),
base_med AS (
  SELECT seg, dow, median(vol) AS med FROM per_day
  WHERE d IN ({base_dates:Array(Date)}) GROUP BY seg, dow
),
expected AS (
  SELECT b.seg, sum(b.med * i.n) AS vol_expected
  FROM base_med b JOIN inc_dow i USING (dow) GROUP BY b.seg
),
actual AS (
  SELECT seg, sum(vol) AS vol_inc FROM per_day
  WHERE d IN ({inc_dates:Array(Date)}) GROUP BY seg
)
SELECT
  a.seg,
  a.vol_inc,
  round(e.vol_expected, 0)                                             AS vol_expected,
  round((a.vol_inc / e.vol_expected - 1) * 100, 2)                     AS pct_change,
  round((a.vol_inc - e.vol_expected)
        / sum(a.vol_inc - e.vol_expected) OVER () * 100, 1)            AS share_of_total_change
FROM actual a
JOIN expected e USING (seg)
ORDER BY pct_change
