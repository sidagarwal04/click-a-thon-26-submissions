-- Q2a · Dimension sweep, ratio levers (fill_rate / render_rate / ctr / ecpm)
-- Fragments: __DIM__  __METRIC_NUM__  __METRIC_DEN__  __SEG_FILTER__   (README whitelist)
-- Params   : {inc_dates:Array(Date)}  {base_dates:Array(Date)}  {datasets:Array(String)}
--            {min_volume:UInt32}  {scale:Float64}   (scale: 1, or 1000 for ecpm)
-- Weight = segment share of the metric's own denominator (den substitution = weight rule).
-- Runner: candidate if |contribution| >= 50% of q1's global delta OR |delta| > 3x next.
--         all deltas flat -> q5 before any GLOBAL verdict.
--         Additivity assert (vs q5.mix): rerun with min_volume=0, no segment dropped.
SELECT
  __DIM__ AS seg,
  round(sumIf(__METRIC_NUM__, event_date IN ({inc_dates:Array(Date)}))
      / nullIf(sumIf(__METRIC_DEN__, event_date IN ({inc_dates:Array(Date)})), 0)
      * {scale:Float64}, 4)                                                     AS val_inc,
  round(sumIf(__METRIC_NUM__, event_date IN ({base_dates:Array(Date)}))
      / nullIf(sumIf(__METRIC_DEN__, event_date IN ({base_dates:Array(Date)})), 0)
      * {scale:Float64}, 4)                                                     AS val_base,
  round(val_inc - val_base, 4)                                                  AS delta,
  sumIf(__METRIC_DEN__, event_date IN ({inc_dates:Array(Date)}))                AS den_inc,
  round(den_inc / sum(den_inc) OVER () * (val_inc - val_base) * 100
        / {scale:Float64}, 4)                                                   AS contribution_pp
FROM rca.ad_events_enriched
WHERE (event_date IN ({inc_dates:Array(Date)}) OR event_date IN ({base_dates:Array(Date)}))
  AND dataset IN ({datasets:Array(String)})
  AND __SEG_FILTER__
  AND __SCOPE_FILTER__
GROUP BY seg
HAVING den_inc > {min_volume:UInt32}
ORDER BY abs(contribution_pp) DESC
