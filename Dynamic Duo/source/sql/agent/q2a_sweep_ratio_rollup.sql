-- Q2ar · Dimension sweep on the ROLLUP (first pass; see README "which table").
-- The dimension is a bound PARAM here (it's data in the long-format rollup), so the
-- runner needs zero fragment substitution for it. Reads a few hundred rows per sweep.
-- Fragments: __NUM_COL__ __DEN_COL__ in {requests, fills, impressions, clicks, revenue}
--            fill_rate: fills/requests · render: impressions/fills ·
--            ctr: clicks/impressions  · ecpm: revenue/impressions (scale 1000)
-- Params   : {dim:String} {inc_dates:Array(Date)} {base_dates:Array(Date)}
--            {min_volume:UInt32} {scale:Float64}
-- '(none)' = unfilled/keyless bucket on advertiser dims - excluded (the rollup
-- counterpart of __SEG_FILTER__). NOTE: no dataset column on the rollup by design.
SELECT
  value AS seg,
  round(sumIf(__NUM_COL__, toDate(window_start) IN ({inc_dates:Array(Date)}))
      / nullIf(sumIf(__DEN_COL__, toDate(window_start) IN ({inc_dates:Array(Date)})), 0)
      * {scale:Float64}, 4)                                                    AS val_inc,
  round(sumIf(__NUM_COL__, toDate(window_start) IN ({base_dates:Array(Date)}))
      / nullIf(sumIf(__DEN_COL__, toDate(window_start) IN ({base_dates:Array(Date)})), 0)
      * {scale:Float64}, 4)                                                    AS val_base,
  round(val_inc - val_base, 4)                                                 AS delta,
  sumIf(__DEN_COL__, toDate(window_start) IN ({inc_dates:Array(Date)}))        AS den_inc,
  round(den_inc / sum(den_inc) OVER () * (val_inc - val_base) * 100
        / {scale:Float64}, 4)                                                  AS contribution_pp
FROM rca.metrics_hourly_by_dim
WHERE dimension = {dim:String}
  AND value != '(none)'
  AND (toDate(window_start) IN ({inc_dates:Array(Date)})
    OR toDate(window_start) IN ({base_dates:Array(Date)}))
GROUP BY seg
HAVING den_inc > {min_volume:UInt32}
ORDER BY abs(contribution_pp) DESC
