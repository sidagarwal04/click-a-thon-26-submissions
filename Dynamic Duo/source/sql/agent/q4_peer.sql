-- Q4 · Peer comparison - history-free, RATIO metrics only
-- (volume anomalies on short slices: compare time buckets within the slice instead)
-- Fragments: __DIM__  __METRIC_NUM__  __METRIC_DEN__  __SEG_FILTER__
-- Params   : {inc_start:DateTime}  {inc_end:DateTime}  {datasets:Array(String)}
--            {thresh:Float64}  {min_volume:UInt32}  {scale:Float64}
-- Runner: runs ONLY when q1.min_clean_days_per_dow < 2 (unseen/short-history path),
-- where q2/q3/q5 are impossible (all need a baseline window). There it does BOTH jobs:
--   pass 1: sweep each dim of the lever -> outlier vs sibling median
--   pass 2: rerun other dims with the outlier excluded via __SCOPE_FILTER__
--           (e.g. "os_version != 'Android 15'") -> shadows collapse = ruled out
-- Not a standing cross-check on the baseline path: detection is authoritative upstream.
SELECT
  __DIM__ AS seg,
  round(sum(__METRIC_NUM__) / nullIf(sum(__METRIC_DEN__), 0) * {scale:Float64}, 4) AS val,
  round(median(val) OVER (), 4)                                                    AS peer_median,
  round(val - peer_median, 4)                                                      AS vs_peer,
  sum(__METRIC_DEN__)                                                              AS den_n,
  multiIf(vs_peer < -{thresh:Float64}, 'ANOMALOUS_LOW',
          vs_peer >  {thresh:Float64}, 'ANOMALOUS_HIGH',
          'NORMAL')                                                                AS verdict
FROM rca.ad_events_enriched
WHERE event_time >= {inc_start:DateTime} AND event_time < {inc_end:DateTime}
  AND dataset IN ({datasets:Array(String)})
  AND __SEG_FILTER__
  AND __SCOPE_FILTER__
GROUP BY seg
HAVING den_n > {min_volume:UInt32}
ORDER BY vs_peer
