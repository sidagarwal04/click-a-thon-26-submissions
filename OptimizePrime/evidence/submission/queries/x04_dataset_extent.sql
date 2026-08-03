-- x04 · What the pipeline actually ingested and modelled for this day.
SELECT
    (SELECT count() FROM ev_raw) AS ev_raw_rows,
    (SELECT sum(distinct_rows) FROM v_quarantine_summary) AS quarantined_events,
    (SELECT count() FROM ev_cast_quarantine) AS cast_rejects,
    (SELECT count() FROM v_ev_model_input) AS accepted_model_input,
    (SELECT count() FROM content_dim FINAL) AS content_rows,
    (SELECT count() FROM session_intervals FINAL) AS session_intervals_rows,
    (SELECT uniqExact(video_session_id) FROM session_intervals FINAL) AS sessions,
    (SELECT uniqExact(user_id) FROM session_intervals FINAL) AS users,
    (SELECT count() FROM cc_minute_delta) AS delta_rows,
    (SELECT count() FROM cc_minute_delta WHERE minute >= '2026-07-31 00:00:00' AND minute < '2026-08-01 00:00:00') AS delta_rows_day,
    (SELECT count() FROM cc_hour_agg FINAL) AS hour_rows,
    (SELECT toString(min(event_timestamp)) FROM ev_raw) AS raw_min_ts,
    (SELECT toString(max(event_timestamp)) FROM ev_raw) AS raw_max_ts,
    (SELECT count(DISTINCT toDate(hour)) FROM cc_hour_agg FINAL) AS output_dates
FORMAT TSVWithNames
