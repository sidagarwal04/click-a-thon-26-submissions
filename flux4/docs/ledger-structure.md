
## Query for schema creation 
CREATE TABLE investigation.ledger (
    run_id UUID,
    trace_id UUID,
    incident_start DateTime64(3),
    incident_end DateTime64(3),
    step_order UInt8,
    step_name String,
    step_type Enum8('detection' = 1, 'decomposition' = 2, 'localization' = 3, 'ruleout' = 4, 'final' = 5),
    metric String,
    dimension String,
    segment String,
    observed_value Float64,
    expected_value Float64,
    delta_value Float64,
    contribution_pct Float64,
    verdict Enum8('anomaly' = 1, 'normal' = 2, 'ruled_out' = 3, 'insufficient_volume' = 4),
    rationale String,
    created_at DateTime64(3)
) ENGINE = MergeTree()
ORDER BY (run_id, step_order);

## Diagnostics query
Querying diagnostics in seconds
For the final output, the common fast queries are:

fetch all rows for a run:
SELECT * FROM investigation.ledger WHERE run_id = ? ORDER BY step_order

fetch anomaly candidates:
WHERE run_id = ? AND verdict = 'anomaly'

fetch final diagnosis row(s):
WHERE run_id = ? AND step_type = 'final'

Because the table is narrow and ordered by (run_id, step_order), ClickHouse can read one run quickly.

## Ledger column definitions
1. run_id — unique identifier for one complete investigation execution (one incident or unseen-slice run)
2. trace_id — optional identifier linking ledger rows to the observability trace or Langfuse session
3. incident_start — start of the incident window being analyzed
4. incident_end — end of the incident window being analyzed
5. step_order — sequence position of this step in the investigation flow
6. step_name — human-readable name of the step, e.g. detect_anomaly, decompose_factors, scan_dimension
7. step_type — categorical stage of the workflow, e.g. detection, decomposition, localization, ruleout, final
8. metric — KPI under test, e.g. revenue, fill_rate, eCPM, requests
9. dimension — dimension being evaluated, e.g. region, app_id, ad_format, geo_device_id
10. segment — specific segment value within the dimension, e.g. NAM, video, app_00123
11. observed_value — the measured metric value in the incident window
12. expected_value — the baseline or predicted value for that same metric/window
13. delta_value — the difference between observed and expected
14. contribution_pct — how much this step/segment contributes to the total anomaly
15. verdict — outcome of the step, e.g. anomaly, normal, ruled_out, insufficient_volume
16. rationale — short explanation of why the step was taken and what it means
17. created_at — timestamp when the ledger row was written