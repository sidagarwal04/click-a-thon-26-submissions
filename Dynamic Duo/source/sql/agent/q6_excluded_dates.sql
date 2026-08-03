-- Q6 · Excluded dates for q1 baselines = the system's own past verdicts (baseline rule 3)
-- Params: {before_date:Date}
-- Only CONFIRMED-cause verdicts exclude a date. Status alone is too blunt a key:
-- hedged short-history verdicts (PEER_OUTLIER) also close as 'diagnosed', and letting
-- them exclude dates starves later baselines chronologically (EDGE_CASES.md "baseline
-- starvation": early hedged verdicts eat the same-weekday pool, everything after them
-- degrades to the peer path, and correctly-seasonal days get re-diagnosed by it).
-- Seasonal/dismissed days are clean and STAY in baselines. Chronological by
-- construction (only verdicts before the incident exist).
SELECT groupUniqArray(d) AS excluded_dates
FROM (
  SELECT arrayJoin(
           arrayMap(x -> toDate(window_start) + x,
                    range(toUInt32(dateDiff('day', toDate(window_start),
                                            toDate(window_end)) + 1)))) AS d
  FROM rca.incidents FINAL
  WHERE status = 'diagnosed'
    AND incident_id IN (
      SELECT incident_id FROM rca.diagnoses FINAL
      WHERE verdict_code IN ('CAUSE_CONFIRMED', 'INTERACTION', 'MIX_SHIFT',
                             'MIX_INTERACTION', 'DEMAND_PULLOUT',
                             'VOLUME_CANDIDATE', 'GLOBAL_MOVEMENT')
    )
    AND toDate(window_start) < {before_date:Date}
)
WHERE d < {before_date:Date}
