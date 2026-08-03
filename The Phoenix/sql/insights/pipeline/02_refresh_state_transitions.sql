-- Rebuild session_state_transitions for every session a window touched.
--
-- Parameters: from_ts, to_ts, tolerance_s. No version param: refresh_insights.sh globs this
-- directory and binds only those three, so version is derived from now64 the way
-- 01_refresh_session_facts.sql does.
--
-- ONE STATEMENT, retract and assert together, for the reason sql/pipeline/03b documents: with two
-- statements a session whose first in-window event arrives between them gets asserted without
-- being retracted, and on Cloud SharedMergeTree the assert's read can miss rows the retract just
-- wrote on another replica. Both put the same edge in twice. Here both branches read the same
-- pinned part set and land as one insert. The retract zeroes any nonzero group in either
-- direction (abs(s) rows of the opposite sign), so a window is self-healing for every session it
-- touches, whatever a previous partial insert left behind.
--
-- ============================================================================================
-- WHY THE SYNTHETIC AND REAL EDGES ARE MERGED BEFORE from_state IS COMPUTED, and not after.
--
-- The obvious construction -- derive the real transitions, derive the stale ones, UNION them --
-- is wrong, and measurably so. from_state has to be the state the session was ACTUALLY in
-- immediately before the edge, and a stale_heartbeat sitting between two real events changes
-- what the next real edge is leaving. Computing from_state over real events only produced, on a
-- one-hour frozen-slice window: an edge `playing_foreground -> stale_heartbeat` ordered AFTER
-- the session's own `-> ended` edge, and both claiming to leave playing_foreground. A session
-- cannot go quiet after it has ended, and two consecutive edges cannot leave the same state.
--
-- So every point -- real or synthetic -- goes into ONE ordered list first, and from_state is a
-- single lag over that list. The chain is then closed by construction: every edge's from_state
-- is the previous edge's to_state, for free, with no reconciliation pass.
-- ============================================================================================

INSERT INTO session_state_transitions
WITH
    {tolerance_s:UInt32} AS tol,

    touched AS
    (
        SELECT DISTINCT video_session_id FROM raw_events
        WHERE event_timestamp >= parseDateTime64BestEffort({from_ts:String}, 3)
          AND event_timestamp <= parseDateTime64BestEffort({to_ts:String}, 3)
    ),

    -- Every event of every touched session, labelled with the state it puts the session INTO.
    -- A neutral heartbeat labels NULL: it proves the client is alive without saying anything
    -- about what the session is doing. That is the same ruling sql/schema/03_event_state.sql
    -- makes and must not diverge from -- treating neutral telemetry as playing_foreground would
    -- cancel a pause with the very next buffer-health row and erase paused time entirely.
    labelled AS
    (
        SELECT
            video_session_id,
            event_timestamp AS ts,
            event_type,
            event,
            multiIf(
                event_type = 'VideoSessionStart',                'created',
                event_type = 'VideoSessionEnd',                  'ended',
                event_type = 'VideoError',                       'error',
                event_type = 'AppBackgrounded',                  'background',
                event_type IN ('AppForegrounded', 'VideoPlay'),  'playing_foreground',
                event_type = 'VideoHeartbeat' AND event IN ('pause','speed-pause','AdPause'),
                                                                 'paused_foreground',
                event_type = 'VideoHeartbeat' AND event IN ('resume','speed-resume','AdResume'),
                                                                 'playing_foreground',
                NULL) AS raw_state,
            -- A reopen is a new playback instance. Counting ends STRICTLY BEFORE this row keeps
            -- the end event itself on the instance it terminated, per decision D13 (last end is
            -- terminal), so a reopen cannot manufacture an `ended -> playing_foreground` edge.
            countIf(event_type = 'VideoSessionEnd') OVER (
                PARTITION BY video_session_id ORDER BY event_timestamp ASC
                ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING) AS instance_no
        FROM raw_events
        WHERE video_session_id IN (SELECT video_session_id FROM touched)
    ),

    carried AS
    (
        SELECT
            video_session_id, ts, event_type, event, instance_no,
            coalesce(
                argMax(raw_state, if(raw_state IS NULL, toDateTime64(0, 3), ts)) OVER w,
                'created') AS state,
            leadInFrame(ts) OVER (PARTITION BY video_session_id, instance_no ORDER BY ts ASC
                                  ROWS BETWEEN CURRENT ROW AND UNBOUNDED FOLLOWING) AS next_ts,
            -- "Is this the instance's last event?" answered by POSITION, not by comparing
            -- timestamps. leadInFrame returns its epoch-0 default past the end, so `next_ts <= ts`
            -- looks like a tail test -- and it also fires whenever two events share a millisecond,
            -- because then next_ts EQUALS ts. 29% of this corpus shares a second (see
            -- sql/schema/03_event_state.sql), so that test manufactured a stale edge on every tie:
            -- measured 150,381 stale edges against a corpus that contains only 5,653 gaps over the
            -- 90s tolerance in total, 0.5 per session, with a p99 gap of 65 seconds.
            row_number() OVER (PARTITION BY video_session_id, instance_no ORDER BY ts ASC) AS rn,
            count()      OVER (PARTITION BY video_session_id, instance_no) AS n_events
        FROM labelled
        WINDOW w AS (PARTITION BY video_session_id, instance_no ORDER BY ts ASC
                     ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
    ),

    -- ONE list of points: every real event, plus a synthetic point wherever the session went
    -- quiet for longer than the tolerance.
    --
    -- The synthetic point is stamped at last_event + tolerance, which is the exact instant the
    -- concurrency model stops counting the session. That is deliberate: this table and the served
    -- curve then agree about when a session went dark by construction, not by coincidence.
    --
    -- Two cases. A GAP: the next event exists but is more than tol away, so the session was dark
    -- from ts+tol until it spoke again -- and if that next event is the VideoSessionEnd, the end
    -- correctly reads as leaving stale_heartbeat rather than leaving playback. A TAIL: there is
    -- no next event at all (leadInFrame yields its epoch-0 default, hence next_ts <= ts) and the
    -- session never ended, so it simply stopped. A session whose last event IS the end gets no
    -- synthetic point -- it did not go quiet, it finished.
    points AS
    (
        SELECT video_session_id, instance_no, ts, state, event_type, event FROM carried
        UNION ALL
        SELECT
            video_session_id, instance_no,
            ts + toIntervalSecond(tol) AS ts,
            'stale_heartbeat'          AS state,
            ''                         AS event_type,
            ''                         AS event
        FROM carried
        WHERE state != 'ended'
          AND ( (rn < n_events AND dateDiff('second', ts, next_ts) > tol)   -- a real gap
                OR rn = n_events )                                          -- the tail
    ),

    -- Collapse the point list to EDGES: keep a point only where it changes the state. Without
    -- this the table would be raw_events with a state column -- 93% of the corpus is heartbeats,
    -- and a Sankey drawn from that is unreadable.
    --
    -- `ord` EXISTS TO MAKE THE WINDOW ORDERING TOTAL, and it is not decoration. Ordering the lag
    -- by (ts, state) leaves genuine ties: two decisive events can share a millisecond, and 29% of
    -- this corpus shares a second. ClickHouse treats rows with identical ORDER BY values as one
    -- PEER GROUP, and lagInFrame steps over the whole group rather than to the adjacent row -- so
    -- a duplicate point could not see its own twin and the dedupe silently passed both. Measured:
    -- two identical `playing_foreground -> paused_foreground` edges at the same instant,
    -- 2026-07-26 11:00:03.514, in a single session. Lagging by a unique row number instead makes
    -- adjacency exact.
    ordered AS
    (
        SELECT
            video_session_id, instance_no, ts, state, event_type, event,
            row_number() OVER (PARTITION BY video_session_id, instance_no
                               ORDER BY ts ASC, state ASC, event_type ASC, event ASC) AS ord
        FROM points
    ),

    edged AS
    (
        SELECT
            video_session_id, instance_no, ts, state, event_type, event, ord,
            lagInFrame(state) OVER (PARTITION BY video_session_id, instance_no ORDER BY ord ASC
                                    ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS prev_state
        FROM ordered
    ),

    -- prev_at is taken AFTER the collapse, never before. seconds_in_previous_state must measure
    -- time spent in the state being LEFT, so it has to lag over edges; lagging over points would
    -- measure the time since the last heartbeat, which is a different and much smaller number.
    transitions AS
    (
        SELECT
            video_session_id, instance_no, ts AS transition_at,
            ifNull(prev_state, '') AS from_state,
            state                  AS to_state,
            event_type             AS trigger_event_type,
            event                  AS trigger_event,
            lagInFrame(ts) OVER (PARTITION BY video_session_id, instance_no ORDER BY ord ASC
                                 ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS prev_at,
            row_number() OVER (PARTITION BY video_session_id, instance_no ORDER BY ord ASC) AS seq
        FROM edged
        WHERE prev_state IS NULL OR state != prev_state
    ),

    -- Dimensions from the session's FIRST event. argMin, not any(): a session whose content row
    -- changed mid-flight must not have its edges split across two dimension variants, which
    -- would double it in every GROUP BY.
    dims AS
    (
        SELECT
            video_session_id,
            argMin(user_id, event_timestamp)     AS user_id,
            argMin(content_id, event_timestamp)  AS content_id,
            argMin(platform, event_timestamp)    AS platform,
            argMin(country, event_timestamp)     AS country,
            argMin(app_version, event_timestamp) AS app_version
        FROM raw_events
        WHERE video_session_id IN (SELECT video_session_id FROM touched)
        GROUP BY video_session_id
    )

-- ASSERT
SELECT
    t.video_session_id,
    toUInt16(t.instance_no + 1) AS playback_instance_no,
    d.user_id, d.content_id, d.platform, d.country, d.app_version,
    c.video_type,
    t.transition_at,
    t.from_state,
    t.to_state,
    t.trigger_event_type,
    t.trigger_event,
    -- Time spent in the state being left. The first edge of an instance has no predecessor;
    -- lagInFrame returns epoch 0 there and dateDiff against 1970 would report ~1.7 billion
    -- seconds, so seq = 1 is pinned to 0.
    if(t.seq = 1, toUInt32(0),
       toUInt32(greatest(dateDiff('second', t.prev_at, t.transition_at), 0))) AS seconds_in_previous_state,
    toUInt32(t.seq) AS transition_sequence,
    -- Decorative on a Collapsing table: collapse is driven by sign, not version. Kept so a row
    -- records which refresh wrote it. Reads must use sum(sign) > 0, never FINAL.
    toUInt64(toUnixTimestamp64Milli(now64(3))) AS version,
    1 AS sign
FROM transitions AS t
INNER JOIN dims    AS d ON t.video_session_id = d.video_session_id
LEFT  JOIN content AS c ON d.content_id = c.content_id

UNION ALL

-- RETRACT
SELECT
    video_session_id, playback_instance_no, user_id, content_id, platform, country, app_version,
    video_type, transition_at, from_state, to_state, trigger_event_type, trigger_event,
    seconds_in_previous_state, transition_sequence, version,
    -toInt8(if(s > 0, 1, -1)) AS sign
FROM
(
    SELECT
        video_session_id, playback_instance_no, user_id, content_id, platform, country,
        app_version, video_type, transition_at, from_state, to_state, trigger_event_type,
        trigger_event, seconds_in_previous_state, transition_sequence, version,
        sum(sign) AS s
    FROM session_state_transitions
    WHERE video_session_id IN (SELECT video_session_id FROM touched)
    GROUP BY video_session_id, playback_instance_no, user_id, content_id, platform, country,
             app_version, video_type, transition_at, from_state, to_state, trigger_event_type,
             trigger_event, seconds_in_previous_state, transition_sequence, version
    HAVING s != 0
)
ARRAY JOIN range(toUInt32(abs(s))) AS _r;
