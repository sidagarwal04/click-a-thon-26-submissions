-- Q1 · WHAT moved? Compares the 4 revenue levers (requests/fill/render/ecpm) vs a
--      same-weekday median baseline, plus log-share attribution across levers.
-- Params : {flagged_dates:Array(Date)}  {excluded_dates:Array(Date)}  {datasets:Array(String)}
-- Returns: one row. Runner decisions:
--   min_clean_days_per_dow < 2       -> no usable baseline: q4 path
--   lever(s) beyond threshold        -> sweep that lever's dims (q2); several levers ->
--                                       largest |log_share| leads, every one over its
--                                       threshold still gets its own investigation
--   no lever beyond threshold        -> DISAGREEMENT with detection: log both sides,
--                                       flag for a human, never a silent close
--   base_days_used                   -> pass verbatim as {base_dates} to q2/q3/q5
WITH
  inc_dates AS (
    SELECT event_date AS d, toDayOfWeek(event_date) AS dow
    FROM rca.ad_events_enriched
    WHERE event_date IN ({flagged_dates:Array(Date)}) AND dataset IN ({datasets:Array(String)})
    GROUP BY d
  ),
  base_days AS (
    SELECT event_date AS d, toDayOfWeek(event_date) AS dow
    FROM rca.ad_events_enriched
    WHERE dataset IN ({datasets:Array(String)})
      AND toDayOfWeek(event_date) IN (SELECT DISTINCT dow FROM inc_dates)
      AND event_date <  (SELECT min(d) FROM inc_dates)
      AND event_date >= addWeeks((SELECT min(d) FROM inc_dates), -4)
      AND event_date NOT IN ({excluded_dates:Array(Date)})
    GROUP BY d, dow
  ),
  inc AS (
    SELECT count() AS req, sum(is_filled) AS fills,
           sum(is_impression) AS imps, sum(revenue) AS rev
    FROM rca.ad_events_enriched
    WHERE event_date IN (SELECT d FROM inc_dates) AND dataset IN ({datasets:Array(String)}) AND __SCOPE_FILTER__
  ),
  base_per_day AS (
    SELECT event_date AS d, toDayOfWeek(event_date) AS dow,
           count() AS req, sum(is_filled) AS fills,
           sum(is_impression) AS imps, sum(revenue) AS rev
    FROM rca.ad_events_enriched
    WHERE event_date IN (SELECT d FROM base_days) AND dataset IN ({datasets:Array(String)}) AND __SCOPE_FILTER__
    GROUP BY d, dow
  ),
  base_per_dow AS (
    SELECT dow, median(req) AS req, median(fills) AS fills,
           median(imps) AS imps, median(rev) AS rev
    FROM base_per_day GROUP BY dow
  ),
  inc_dow_counts AS (SELECT dow, count() AS n FROM inc_dates GROUP BY dow),
  base AS (
    SELECT sum(b.req * i.n) AS req, sum(b.fills * i.n) AS fills,
           sum(b.imps * i.n) AS imps, sum(b.rev * i.n) AS rev
    FROM base_per_dow b JOIN inc_dow_counts i USING (dow)
  ),
  pool_check AS (SELECT dow, count() AS clean_days FROM base_per_day GROUP BY dow),
  lg AS (
    SELECT log(inc.req / base.req)                                  AS d_req,
           log((inc.fills / inc.req)   / (base.fills / base.req))   AS d_fill,
           log((inc.imps  / inc.fills) / (base.imps  / base.fills)) AS d_render,
           log((inc.rev   / inc.imps)  / (base.rev   / base.imps))  AS d_ecpm,
           log(inc.rev / base.rev)                                  AS d_rev,
           isFinite(d_req + d_fill + d_render + d_ecpm + d_rev)     AS shares_valid
    FROM inc, base
  )
SELECT
  round((inc.req / base.req - 1) * 100, 2)                                        AS requests_pct,
  round((inc.fills/inc.req - base.fills/base.req) * 100, 3)                       AS fill_rate_delta_pp,
  round((inc.imps/nullIf(inc.fills,0) - base.imps/nullIf(base.fills,0)) * 100, 3) AS render_rate_delta_pp,
  round(inc.rev/nullIf(inc.imps,0)*1000 - base.rev/nullIf(base.imps,0)*1000, 4)   AS ecpm_delta,
  round((inc.rev / base.rev - 1) * 100, 2)                                        AS revenue_pct,
  round(inc.fills / inc.req, 4)                                                   AS inc_fill_rate,
  round(base.fills / base.req, 4)                                                 AS base_fill_rate,
  inc.req                                                                         AS inc_requests,
  round(base.req, 0)                                                              AS base_requests_expected,
  if(abs(lg.d_rev) < 0.01 OR NOT lg.shares_valid, NULL, round(lg.d_req    / lg.d_rev * 100, 1)) AS log_share_requests,
  if(abs(lg.d_rev) < 0.01 OR NOT lg.shares_valid, NULL, round(lg.d_fill   / lg.d_rev * 100, 1)) AS log_share_fill,
  if(abs(lg.d_rev) < 0.01 OR NOT lg.shares_valid, NULL, round(lg.d_render / lg.d_rev * 100, 1)) AS log_share_render,
  if(abs(lg.d_rev) < 0.01 OR NOT lg.shares_valid, NULL, round(lg.d_ecpm   / lg.d_rev * 100, 1)) AS log_share_ecpm,
  round(lg.d_rev, 4)                                                              AS revenue_log_delta,
  (SELECT min(coalesce(p.clean_days, 0))
   FROM inc_dow_counts i LEFT JOIN pool_check p USING (dow))                      AS min_clean_days_per_dow,
  (SELECT groupArray(d) FROM (SELECT d FROM base_days ORDER BY d))                AS base_days_used
FROM inc, base, lg
