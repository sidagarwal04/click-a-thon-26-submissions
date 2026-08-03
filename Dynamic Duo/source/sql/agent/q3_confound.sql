-- Q3 · Confounder elimination: re-sweep __DIM__ with the candidate excluded
-- Fragments: __DIM__  __METRIC_NUM__  __METRIC_DEN__  __SEG_FILTER__
--            __CANDIDATE_COL__ (the candidate's own dimension column)
-- Params   : {inc_dates:Array(Date)}  {base_dates:Array(Date)}  {datasets:Array(String)}
--            {candidate_value:String}  {scale:Float64}
-- Runner: dimension RULED OUT if max |delta_excl_candidate| < metric noise threshold
--         (0.005 for fill rate). Record before/after pairs verbatim for the narrative.
SELECT
  __DIM__ AS seg,
  round(sumIf(__METRIC_NUM__, event_date IN ({inc_dates:Array(Date)}))
      / nullIf(sumIf(__METRIC_DEN__, event_date IN ({inc_dates:Array(Date)})), 0)
      * {scale:Float64}, 4)                                            AS val_inc,
  round(sumIf(__METRIC_NUM__, event_date IN ({base_dates:Array(Date)}))
      / nullIf(sumIf(__METRIC_DEN__, event_date IN ({base_dates:Array(Date)})), 0)
      * {scale:Float64}, 4)                                            AS val_base,
  round(val_inc - val_base, 4)                                         AS delta_excl_candidate
FROM rca.ad_events_enriched
WHERE (event_date IN ({inc_dates:Array(Date)}) OR event_date IN ({base_dates:Array(Date)}))
  AND dataset IN ({datasets:Array(String)})
  AND __SEG_FILTER__
  AND __SCOPE_FILTER__
  AND __CANDIDATE_COL__ != {candidate_value:String}
GROUP BY seg
ORDER BY delta_excl_candidate
