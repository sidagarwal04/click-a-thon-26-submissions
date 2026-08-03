-- queries/validate_source_contract.sql — the source-contract gate (ADR 0026).
-- READ-ONLY BY DESIGN: SELECTs only. It asserts and reports what is true about
-- ev_raw / content_dim in the connected database — verdict material as a table
-- of counts — and never modifies, cleans or rejects a row. Treatment of bad
-- rows is sql/15_normalise.sql's decision; loader shape handling is tools/load.sh's.
-- Run via tools/validate-source-contract.sh, which renders __VOCAB_PAIRS__ from
-- evidence/liveness/vocabulary.tsv and computes the verdict. Bare execution of
-- this file fails: the placeholder is not valid SQL. Adapted from
-- feat/problem-space-research queries/validate_source_contract.sql
-- (design-bakeoff cherry-pick #1); its throwIf hard-abort is gone (a report,
-- not a rejection) and its ingested_at clock-skew check is replaced by a
-- wall-clock one: ingested_at is not in the source contract or sql/00_schema.sql
-- (sonyliv alone carries it, ALTERed on 2026-08-01 19:16:50 by the rejected
-- branch's tooling — ADR 0026 §what-happened), and for rows loaded before an
-- ALTER a DEFAULT now64(3) is computed at READ time, so the comparison would be
-- against the current wall clock anyway. Only meaningful under real streaming
-- ingestion, which this pipeline does not do.
--
-- Severity contract (the split that keeps the gate usable at 2am):
--   FAIL — this file is not what we think it is. Stop before spending the hour.
--   WARN — unusual; proceed with eyes open, compare against the committed
--          baseline in evidence/source-contract/.
--   INFO — context for that comparison (volume, span, histogram).
WITH
    ['content_id', 'video_session_id', 'user_id', 'event_type', 'event',
     'event_timestamp', 'platform', 'app_version', 'country', 'audio_language',
     'subtitle_language', 'player_version', 'session_start_epoch'] AS expected_cols,
    (
        SELECT groupArray(name)
        FROM system.columns
        WHERE database = currentDatabase() AND table = 'ev_raw'
    ) AS actual_cols,
    arrayFilter(c -> NOT has(actual_cols, c), expected_cols) AS missing_cols,
    arrayFilter(c -> NOT has(expected_cols, c), actual_cols) AS extra_cols,
    -- The 47-pair vocabulary contract (doubts/11), rendered from
    -- evidence/liveness/vocabulary.tsv by the runner.
    [__VOCAB_PAIRS__] AS known_pairs,
    arrayDistinct(arrayMap(p -> tupleElement(p, 1), known_pairs)) AS known_types,
    (
        SELECT arrayFilter(x -> x != '',
            [if(count() > 0 AND countIf(platform = '')          = count(), 'platform', ''),
             if(count() > 0 AND countIf(country = '')           = count(), 'country', ''),
             if(count() > 0 AND countIf(app_version = '')       = count(), 'app_version', ''),
             if(count() > 0 AND countIf(audio_language = '')    = count(), 'audio_language', ''),
             if(count() > 0 AND countIf(subtitle_language = '') = count(), 'subtitle_language', ''),
             if(count() > 0 AND countIf(player_version = '')    = count(), 'player_version', ''),
             if(count() > 0 AND countIf(event = '')             = count(), 'event', '')])
        FROM ev_raw
    ) AS all_empty_dims,
    session_shape AS
    (
        SELECT
            video_session_id,
            min(event_timestamp) AS first_event_at,
            min(session_start_epoch) AS declared_start_at,
            uniqExact(session_start_epoch) AS incarnations,
            countIf(event_type = 'VideoSessionStart') AS start_events,
            countIf(event_type = 'VideoSessionEnd') AS end_events,
            minIf(event_timestamp, event_type = 'VideoSessionStart') AS first_start_at,
            minIf(event_timestamp, event_type = 'VideoSessionEnd') AS first_end_at
        FROM ev_raw
        GROUP BY video_session_id
    ),
    tied AS
    (
        SELECT count() AS groups, countIf(bad) AS conflicts
        FROM
        (
            SELECT
                video_session_id,
                event_timestamp,
                (uniqExact(platform) > 1 OR uniqExact(country) > 1 OR uniqExact(content_id) > 1) AS bad
            FROM ev_raw
            GROUP BY video_session_id, event_timestamp
        )
    )
SELECT severity, probe, n, note
FROM
(
    SELECT 1 AS ord, 'FAIL' AS severity, 'ev_raw is empty' AS probe,
        toUInt64((SELECT count() FROM ev_raw) = 0) AS n,
        'nothing to validate — wrong file, wrong database, or a failed load' AS note
    UNION ALL
    SELECT 2, 'FAIL', 'timestamp outside 2020..2035',
        (SELECT countIf(toYear(event_timestamp) NOT BETWEEN 2020 AND 2035) FROM ev_raw),
        (SELECT concat('epoch-zero or millis-not-divided; raw span ',
                       toString(min(event_timestamp)), ' -> ', toString(max(event_timestamp))) FROM ev_raw)
    UNION ALL
    SELECT 3, 'FAIL', 'epoch-zero session_start_epoch',
        (SELECT countIf(session_start_epoch = toDateTime64(0, 3)) FROM ev_raw),
        ''
    UNION ALL
    SELECT 4, 'FAIL', 'empty identity (session or user id)',
        (SELECT count() FROM ev_raw WHERE video_session_id = '' OR user_id = ''),
        'rows the session/user tiers cannot attribute'
    UNION ALL
    SELECT 5, 'FAIL', 'unknown event_type (outside the 7)',
        (SELECT count() FROM ev_raw WHERE NOT has(known_types, toString(event_type))),
        (SELECT if(count() = 0, '', concat('new: ', arrayStringConcat(groupUniqArray(5)(toString(event_type)), ', ')))
         FROM ev_raw WHERE NOT has(known_types, toString(event_type)))
    UNION ALL
    SELECT 6, 'FAIL', 'expected columns missing from ev_raw',
        toUInt64(length(missing_cols)),
        if(length(missing_cols) = 0, '', arrayStringConcat(missing_cols, ', '))
    UNION ALL
    SELECT 7, 'WARN', 'columns beyond the 13-column contract',
        toUInt64(length(extra_cols)),
        if(length(extra_cols) = 0, '', concat(arrayStringConcat(extra_cols, ', '),
            ' — DDL drift vs sql/00_schema.sql; CSV-header shape is the loader''s phase-0 check (T1)'))
    UNION ALL
    SELECT 8, 'WARN', 'vocabulary drift: unknown event values',
        (SELECT count() FROM ev_raw
         WHERE has(known_types, toString(event_type))
           AND NOT has(known_pairs, (toString(event_type), toString(event)))),
        (SELECT if(count() = 0, '', concat(toString(count()), ' new pair(s), top: ',
                arrayStringConcat(groupArray(5)(concat(t, '/', e, 'x', toString(c))), ', '),
                ' — unknown events FAIL OPEN and extend activity (doubts/11)'))
         FROM (SELECT toString(event_type) AS t, toString(event) AS e, count() AS c
               FROM ev_raw
               WHERE has(known_types, toString(event_type))
                 AND NOT has(known_pairs, (toString(event_type), toString(event)))
               GROUP BY event_type, event ORDER BY c DESC))
    UNION ALL
    SELECT 9, 'WARN', 'reused video_session_id (>1 session_start_epoch)',
        (SELECT countIf(incarnations > 1) FROM session_shape),
        'two lifecycles under one id merge into one session'
    UNION ALL
    SELECT 10, 'WARN', 'events before declared session start',
        (SELECT countIf(first_event_at < declared_start_at) FROM session_shape),
        'sessions; the model derives starts from event timestamps, not this column'
    UNION ALL
    SELECT 11, 'WARN', 'future-dated events (> now + 5 min)',
        (SELECT countIf(event_timestamp > now64(3) + INTERVAL 5 MINUTE) FROM ev_raw),
        'wall-clock skew; synthetic rehearsal days trip this by design'
    UNION ALL
    SELECT 12, 'WARN', 'VideoSessionEnd before VideoSessionStart',
        (SELECT countIf(start_events > 0 AND end_events > 0 AND first_end_at < first_start_at) FROM session_shape),
        'sessions; out-of-order lifecycle markers'
    UNION ALL
    SELECT 13, 'WARN', 'multiple VideoSessionEnd in one session',
        (SELECT countIf(end_events > 1) FROM session_shape),
        'sessions; the end marker is an idempotent hard stop in the model'
    UNION ALL
    SELECT 14, 'WARN', 'tied dimensions at one (session, timestamp)',
        (SELECT conflicts FROM tied),
        (SELECT if(groups = 0, '', concat(toString(round(conflicts / groups * 100, 4)),
            '% of groups disagree on platform/country/content — ADR 0009 vote assumes this is rare')) FROM tied)
    UNION ALL
    SELECT 15, 'WARN', 'exact duplicate rows (retry copies)',
        (SELECT count() - uniqExact((content_id, video_session_id, user_id, event_type, event,
            event_timestamp, platform, app_version, country, audio_language, subtitle_language,
            player_version, session_start_epoch)) FROM ev_raw),
        'dedup proven inert for totals/peak but NOT at filter grain (doubts/06)'
    UNION ALL
    SELECT 16, 'WARN', 'sentinel collision: content_id = -1 events',
        (SELECT count() FROM ev_raw WHERE content_id = -1),
        'cube rows are safe (cube_level, ADR 0022) but the p_* = -1 query API stays ambiguous (R9)'
    UNION ALL
    SELECT 17, 'WARN', 'literal * in platform or country',
        (SELECT count() FROM ev_raw WHERE platform = '*' OR country = '*'),
        'collides with the all-rollup sentinel of the query API (sql/85_windows.sql)'
    UNION ALL
    -- __CONTENT_DIM__ renders to content_dim, or to an empty relation when the
    -- table is absent (content passed as 'none', A9) — then every id counts as
    -- unresolved, which is exactly what serving would do.
    SELECT 18, 'WARN', 'event content_id absent from content_dim',
        (SELECT uniqExact(content_id) FROM ev_raw
         WHERE content_id NOT IN (SELECT content_id FROM __CONTENT_DIM__)),
        'distinct ids; they serve (unknown) titles, joins do not error (R10)'
    UNION ALL
    SELECT 19, 'WARN', 'conflicting content_dim definitions',
        (SELECT count() FROM (SELECT content_id FROM __CONTENT_DIM__
            GROUP BY content_id HAVING uniqExact((title, video_type, category)) > 1)),
        'ReplacingMergeTree picks arbitrarily between conflicting rows'
    UNION ALL
    SELECT 20, 'WARN', 'dimension column entirely empty',
        toUInt64(length(all_empty_dims)),
        if(length(all_empty_dims) = 0, '', concat(arrayStringConcat(all_empty_dims, ', '),
            ' — a CSV column missing at load silently becomes empty strings (T1 owns the loader)'))
    UNION ALL
    SELECT 21, 'INFO', 'rows',
        (SELECT count() FROM ev_raw), ''
    UNION ALL
    SELECT 22, 'INFO', 'sessions / users',
        (SELECT uniqExact(video_session_id) FROM ev_raw),
        (SELECT concat(toString(uniqExact(user_id)), ' distinct users') FROM ev_raw)
    UNION ALL
    SELECT 23, 'INFO', 'span (minutes)',
        (SELECT toUInt64(greatest(dateDiff('minute', min(event_timestamp), max(event_timestamp)), 0)) FROM ev_raw),
        (SELECT concat(toString(min(event_timestamp)), ' -> ', toString(max(event_timestamp))) FROM ev_raw)
    UNION ALL
    SELECT 24, 'INFO', 'event_type histogram',
        (SELECT uniqExact(event_type) FROM ev_raw),
        (SELECT arrayStringConcat(groupArray(concat(t, ':', toString(c))), ' ')
         FROM (SELECT toString(event_type) AS t, count() AS c FROM ev_raw
               GROUP BY event_type ORDER BY c DESC))
    UNION ALL
    SELECT 25, 'INFO', 'distinct content ids',
        (SELECT uniqExact(content_id) FROM ev_raw),
        (SELECT concat('platforms ', toString(uniqExact(platform)),
                       ' - countries ', toString(uniqExact(country))) FROM ev_raw)
)
ORDER BY ord
FORMAT TSV
