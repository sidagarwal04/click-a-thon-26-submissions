-- Canonical metric expressions. Ratios are sum/sum over the group — never avg of ratios.
-- Reuse these fragments everywhere so no one reinvents a formula (see metrics_glossary.md).

-- fill_rate    :  sum(is_filled) / count(*)
-- render_rate  :  sum(is_impression) / sum(is_filled)
-- ctr          :  sum(is_click) / sum(is_impression)
-- ecpm         :  sum(revenue) / sum(is_impression) * 1000
-- rpr          :  sum(revenue) / count(*)
-- revenue      :  sum(revenue)

-- On the hourly rollup the numerators/denominators are already summed:
-- fill_rate    :  sum(fills) / sum(requests)
-- ctr          :  sum(clicks) / sum(impressions)
-- ecpm         :  sum(revenue) / sum(impressions) * 1000
