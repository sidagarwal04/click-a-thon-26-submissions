// Package mock serves two interactive event producers over HTTP: a load
// simulator that drives internal/generator, and a manual stepper that sends one
// event at a time so playback state can be exercised by hand.
package mock

import (
	"context"
	"fmt"
	"time"

	"github.com/ClickHouse/clickhouse-go/v2"

	"github.com/sonyliv-clickathon/ingest/internal/chx"
)

// TimelineRow is one event of a session with the derived state that holds
// immediately after it.
//
// The state is computed in ClickHouse, not here and not in the browser. That is
// the whole point of this type: a second implementation of the predicate in Go or
// JavaScript could silently disagree with the pipeline, which would make the
// dashboard confidently wrong. Reading it back from the server makes the UI a live
// oracle for the real semantics instead.
type TimelineRow struct {
	EventTS    time.Time `json:"event_ts"`
	EventType  string    `json:"event_type"`
	Event      string    `json:"event"`
	Signal     string    `json:"signal"`
	IsLiveness bool      `json:"is_liveness"`

	Started    bool `json:"started"`
	EndSeen    bool `json:"end_seen"`
	Foreground bool `json:"foreground"`
	Playing    bool `json:"playing"`

	LastEligibleSignal time.Time `json:"last_eligible_signal"`
	LeaseExpires       time.Time `json:"lease_expires"`
	// Active is the full policy predicate: started AND NOT end_seen AND
	// foreground AND playing AND within the lease. This is the column the UI
	// colours a row by.
	Active bool `json:"active"`
}

// Interval is one active range of a session, half-open [start, end).
type Interval struct {
	Start time.Time `json:"start"`
	End   time.Time `json:"end"`
}

// Timeline returns every event of one session with the running derived state.
//
// The CTE chain mirrors concurrency/sql/010_recompute_sessions.sql exactly —
// same signal classification, same stop-wins precedence, same independent
// foreground/playing booleans, same lease.
//
// Filters on sipHash64({vsid}) rather than taking a precomputed key: session_key
// is MATERIALIZED as sipHash64(video_session_id) server-side, and reimplementing
// ClickHouse's SipHash in Go would be a second definition that could disagree.
// Letting the server hash the literal keeps the predicate on the leading
// sort-key column, so this stays a point lookup.
func Timeline(ctx context.Context, c *chx.Client, videoSessionID string, timeoutMS int64) ([]TimelineRow, error) {
	sql := fmt.Sprintf(`
WITH
    {timeout:Int64} AS timeout_ms,
    scoped AS (
        SELECT event_ts, signal,
               signal IN ('play','resume','liveness') AS is_liveness,
               event_type, event
        FROM %s.events_dedup
        WHERE session_key = sipHash64({vsid:String})
    ),
    -- Collapse the millisecond, then apply stop-wins precedence. Both halves are
    -- required: events_dedup returns one row per (session, ts, type, event), so a
    -- single instant can still hold a background and a pause together.
    instants AS (
        -- Display columns are NOT aliased back to their input names. An output
        -- alias that shadows an input column gets resolved inside the aggregate's
        -- own arguments, which fails with "aggregate function is found inside
        -- another aggregate function" — the same trap events_dedup documents for
        -- row_version.
        --
        -- Joined rather than picked: when several events share a millisecond the
        -- UI should show all of them. A rate change renders as
        -- "speed-pause+speed-resume", which is the whole point of that button.
        SELECT event_ts,
               arrayStringConcat(arraySort(groupUniqArray(event_type)), '+')       AS instant_types,
               arrayStringConcat(arraySort(groupUniqArray(event)), '+')            AS instant_events,
               arrayStringConcat(arraySort(groupUniqArray(toString(signal))), '+') AS instant_signals,
               max(signal = 'session_start')                 AS has_start,
               max(signal = 'session_end')                   AS has_end,
               max(signal = 'background')                    AS has_background,
               max(signal = 'foreground')                    AS has_foreground,
               max(signal IN ('pause','error'))              AS has_play_stop,
               max(signal IN ('play','resume'))              AS has_play_start,
               max(is_liveness)                              AS has_liveness
        FROM scoped
        GROUP BY event_ts
    ),
    setters AS (
        SELECT *,
               multiIf(has_end OR has_background, toInt8(-1),
                       has_start OR has_foreground, toInt8(1), toInt8(0)) AS fg_setter,
               multiIf(has_end OR has_play_stop, toInt8(-1),
                       has_play_start, toInt8(1), toInt8(0))              AS play_setter
        FROM instants
    ),
    stated AS (
        SELECT *,
               max(has_start) OVER w                                          AS started,
               max(has_end)   OVER w                                          AS end_seen,
               argMaxIf(fg_setter,   event_ts, fg_setter   != 0) OVER w        AS fg_state,
               argMaxIf(play_setter, event_ts, play_setter != 0) OVER w        AS play_state
        FROM setters
        WINDOW w AS (ORDER BY event_ts ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
    ),
    leased AS (
        SELECT *,
               maxIf(event_ts,
                     has_liveness AND started = 1 AND end_seen = 0
                     AND fg_state = 1 AND play_state = 1) OVER
                   (ORDER BY event_ts ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
                   AS last_eligible
        FROM stated
    )
SELECT
    event_ts,
    instant_types   AS event_type,
    instant_events  AS event,
    instant_signals AS signal,
    has_liveness,
    started = 1                    AS started_b,
    end_seen = 1                   AS end_seen_b,
    fg_state = 1                   AS foreground_b,
    play_state = 1                 AS playing_b,
    last_eligible,
    if(last_eligible > toDateTime64(0, 3, 'UTC'),
       last_eligible + toIntervalMillisecond(timeout_ms),
       toDateTime64(0, 3, 'UTC'))  AS lease_expires,
    started = 1 AND end_seen = 0 AND fg_state = 1 AND play_state = 1
      AND last_eligible > toDateTime64(0, 3, 'UTC')
      AND event_ts < last_eligible + toIntervalMillisecond(timeout_ms) AS active_b
FROM leased
ORDER BY event_ts`, c.Database)

	rows, err := c.Conn.Query(ctx, sql,
		clickhouse.Named("vsid", videoSessionID),
		clickhouse.Named("timeout", timeoutMS))
	if err != nil {
		return nil, fmt.Errorf("timeline: %w", err)
	}
	defer rows.Close()

	out := make([]TimelineRow, 0, 32)
	for rows.Next() {
		var r TimelineRow
		if err := rows.Scan(&r.EventTS, &r.EventType, &r.Event, &r.Signal, &r.IsLiveness,
			&r.Started, &r.EndSeen, &r.Foreground, &r.Playing,
			&r.LastEligibleSignal, &r.LeaseExpires, &r.Active); err != nil {
			return nil, fmt.Errorf("scan timeline row: %w", err)
		}
		out = append(out, r)
	}
	return out, rows.Err()
}

// Intervals returns the active ranges of one session.
//
// Same derivation as Timeline, carried through to segments and merged into
// islands. Segments provably cannot overlap — an interval's end is at most the
// next event's timestamp — so consecutive-run detection is a lag comparison
// rather than a running maximum.
func Intervals(ctx context.Context, c *chx.Client, videoSessionID string, timeoutMS int64, asOf time.Time) ([]Interval, error) {
	sql := fmt.Sprintf(`
WITH
    {timeout:Int64} AS timeout_ms,
    toDateTime64({as_of:String}, 3, 'UTC') AS as_of,
    scoped AS (
        SELECT event_ts, signal, signal IN ('play','resume','liveness') AS is_liveness
        FROM %s.events_dedup WHERE session_key = sipHash64({vsid:String}) AND event_ts <= as_of
    ),
    instants AS (
        SELECT event_ts,
               max(signal = 'session_start')     AS has_start,
               max(signal = 'session_end')       AS has_end,
               max(signal = 'background')        AS has_background,
               max(signal = 'foreground')        AS has_foreground,
               max(signal IN ('pause','error'))  AS has_play_stop,
               max(signal IN ('play','resume'))  AS has_play_start,
               max(is_liveness)                  AS has_liveness
        FROM scoped GROUP BY event_ts
    ),
    setters AS (
        SELECT *,
               multiIf(has_end OR has_background, toInt8(-1),
                       has_start OR has_foreground, toInt8(1), toInt8(0)) AS fg_setter,
               multiIf(has_end OR has_play_stop, toInt8(-1),
                       has_play_start, toInt8(1), toInt8(0))              AS play_setter
        FROM instants
    ),
    stated AS (
        SELECT *,
               max(has_start) OVER w AS started,
               max(has_end)   OVER w AS end_seen,
               argMaxIf(fg_setter,   event_ts, fg_setter   != 0) OVER w AS fg_state,
               argMaxIf(play_setter, event_ts, play_setter != 0) OVER w AS play_state
        FROM setters
        WINDOW w AS (ORDER BY event_ts ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
    ),
    leased AS (
        SELECT *,
               maxIf(event_ts, has_liveness AND started = 1 AND end_seen = 0
                     AND fg_state = 1 AND play_state = 1) OVER
                   (ORDER BY event_ts ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS last_eligible,
               leadInFrame(event_ts, 1, as_of + toIntervalMillisecond(timeout_ms)) OVER
                   (ORDER BY event_ts ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING) AS next_ts
        FROM stated
    ),
    segments AS (
        SELECT event_ts AS s,
               least(next_ts, last_eligible + toIntervalMillisecond(timeout_ms)) AS e
        FROM leased
        WHERE started = 1 AND end_seen = 0 AND fg_state = 1 AND play_state = 1
          AND last_eligible > toDateTime64(0, 3, 'UTC')
          AND event_ts < last_eligible + toIntervalMillisecond(timeout_ms)
    ),
    marked AS (
        SELECT *, s > lagInFrame(e, 1, toDateTime64(0, 3, 'UTC')) OVER
            (ORDER BY s, e ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS new_island
        FROM segments WHERE e > s
    ),
    numbered AS (
        SELECT *, sum(new_island) OVER
            (ORDER BY s, e ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS island
        FROM marked
    )
SELECT min(s) AS start_time, max(e) AS end_time
FROM numbered GROUP BY island ORDER BY start_time`, c.Database)

	rows, err := c.Conn.Query(ctx, sql,
		clickhouse.Named("vsid", videoSessionID),
		clickhouse.Named("timeout", timeoutMS),
		clickhouse.Named("as_of", asOf.UTC().Format("2006-01-02 15:04:05.000")))
	if err != nil {
		return nil, fmt.Errorf("intervals: %w", err)
	}
	defer rows.Close()

	out := make([]Interval, 0, 8)
	for rows.Next() {
		var iv Interval
		if err := rows.Scan(&iv.Start, &iv.End); err != nil {
			return nil, fmt.Errorf("scan interval: %w", err)
		}
		out = append(out, iv)
	}
	return out, rows.Err()
}

// CurvePoint is one minute of the live activity estimate.
type CurvePoint struct {
	Minute   time.Time `json:"minute"`
	Sessions uint64    `json:"sessions"`
	Events   uint64    `json:"events"`
}

// Curve returns sessions with a liveness signal in each of the last n minutes.
//
// This is NOT served concurrency. It is the session-independent lease estimate,
// which on the tuning extract peaks at 3,162 against an exact 2,305 — 37% high.
// The UI must label it as an estimate; the exact answer needs the minute layer,
// which is not deployed yet. Cheap on purpose: one GROUP BY, no coverage
// explosion, so it can be polled while a load run is in flight.
func Curve(ctx context.Context, c *chx.Client, minutes int) ([]CurvePoint, error) {
	if minutes <= 0 || minutes > 720 {
		minutes = 30
	}
	sql := fmt.Sprintf(`
		SELECT toStartOfMinute(event_ts) AS m,
		       uniqExact(session_key)    AS sessions,
		       count()                   AS events
		FROM %s.events_clean
		WHERE event_ts >= now() - toIntervalMinute({mins:Int32})
		  AND signal IN ('play','resume','liveness')
		GROUP BY m ORDER BY m`, c.Database)

	rows, err := c.Conn.Query(ctx, sql, clickhouse.Named("mins", int32(minutes)))
	if err != nil {
		return nil, fmt.Errorf("curve: %w", err)
	}
	defer rows.Close()

	out := make([]CurvePoint, 0, minutes)
	for rows.Next() {
		var p CurvePoint
		if err := rows.Scan(&p.Minute, &p.Sessions, &p.Events); err != nil {
			return nil, fmt.Errorf("scan curve point: %w", err)
		}
		out = append(out, p)
	}
	return out, rows.Err()
}
