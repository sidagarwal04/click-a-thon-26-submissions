-- Q5 · Mix-shift check (Kitagawa): within + mix + interaction = total (exact identity)
-- Fragments: __DIM__  __METRIC_NUM__  __METRIC_DEN__  __SEG_FILTER__
-- Params   : {inc_dates:Array(Date)}  {base_dates:Array(Date)}  {datasets:Array(String)}  {scale:Float64}
-- Weights are den-shares (the metric's own denominator). coalesce guards keep the
-- identity exact for segments that appear/vanish between windows.
-- Runner: assert |within+mix+interaction-total| < 0.001; verdict by dominant term.
WITH seg_stats AS (
  SELECT __DIM__ AS seg,
    sumIf(__METRIC_DEN__, event_date IN ({inc_dates:Array(Date)}))  AS den_inc,
    sumIf(__METRIC_DEN__, event_date IN ({base_dates:Array(Date)})) AS den_base,
    sumIf(__METRIC_NUM__, event_date IN ({inc_dates:Array(Date)}))
      / nullIf(den_inc, 0) * {scale:Float64}                        AS val_inc_raw,
    sumIf(__METRIC_NUM__, event_date IN ({base_dates:Array(Date)}))
      / nullIf(den_base, 0) * {scale:Float64}                       AS val_base_raw
  FROM rca.ad_events_enriched
  WHERE (event_date IN ({inc_dates:Array(Date)}) OR event_date IN ({base_dates:Array(Date)}))
    AND dataset IN ({datasets:Array(String)})
    AND __SEG_FILTER__
  AND __SCOPE_FILTER__
  GROUP BY seg
),
shares AS (
  SELECT seg,
         coalesce(val_inc_raw,  val_base_raw) AS val_inc,
         coalesce(val_base_raw, val_inc_raw)  AS val_base,
         den_inc  / (SELECT sum(den_inc)  FROM seg_stats) AS w_inc,
         den_base / (SELECT sum(den_base) FROM seg_stats) AS w_base
  FROM seg_stats
)
SELECT
  round(sum(w_base * (val_inc - val_base)) * 100 / {scale:Float64}, 3)           AS within_effect_pp,
  round(sum((w_inc - w_base) * val_base) * 100 / {scale:Float64}, 3)             AS mix_effect_pp,
  round(sum((w_inc - w_base) * (val_inc - val_base)) * 100 / {scale:Float64}, 3) AS interaction_pp,
  round((sum(w_inc * val_inc) - sum(w_base * val_base)) * 100 / {scale:Float64}, 3) AS total_delta_pp
FROM shares
