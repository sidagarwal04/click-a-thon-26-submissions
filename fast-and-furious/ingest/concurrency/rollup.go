// Package concurrency turns the event stream into the two tables a dashboard
// reads.
//
// It owns three steps, deliberately separated because they have different cost
// and different correctness properties:
//
//	intervals  events_dedup -> session_intervals    per-session, ORDER-DEPENDENT
//	live       session_intervals -> 10s serving      order-free, best-effort
//	minute     session_intervals -> 1m serving       order-free, corrected
//
// The SQL lives in sql/ and is embedded, so a deployed binary carries its own
// pipeline and there is nothing to copy to the box alongside it. It is embedded
// from HERE rather than from ingest/sql/ for one reason: everything in ingest/sql
// is idempotent DDL that `sonyliv-ingest schema` applies in filename order, and
// these are parameterized INSERTs that must never be swept up by that.
package concurrency

import (
	"context"
	"embed"
	"fmt"
	"io/fs"
	"sort"
	"strings"
	"time"

	"github.com/sonyliv-clickathon/ingest/internal/chx"
)

//go:embed all:sql
var sqlFS embed.FS

// DefaultPolicyVersion names the semantic contract the intervals are computed
// under. It is stamped onto every session_intervals row and every watermark, so a
// change in meaning is visible in the data rather than only in a commit message.
const DefaultPolicyVersion = "sonyliv-active-v1"

// DefaultHeartbeatTimeoutMS is the liveness lease. 120s is the measured policy
// (solution/policy.yaml), not the 60s the dataset documentation claims — source
// p50 heartbeat cadence is 40s and a 60s lease strands ordinary sessions.
const DefaultHeartbeatTimeoutMS = 120_000

// LiveLookbackDays bounds how far back the rollups scan session_intervals.
//
// session_intervals partitions on the session's START date, but the rollups
// filter on interval time, so a session that opened days ago can still be active
// inside the window being built. The longest session in the extract runs 43.64h,
// so two days would already be enough; three leaves headroom without widening the
// scan meaningfully.
const LiveLookbackDays = 3

// LiveBucket is the live layer's grain. It MUST match the bucket_ms literal in
// sql/020_rollup_live.sql; Live() aligns its window to this, and a mismatch would
// silently produce partial buckets again.
const LiveBucket = 10 * time.Second

// MinuteBucket is the lagged layer's grain, and MUST match the bucket_ms literal
// in sql/030_rollup_minute.sql. Minute() aligns its publish cutoff to this for the
// same reason Live() aligns its window: a cutoff landing mid-bucket publishes a
// partial bucket, which is worse than publishing nothing.
const MinuteBucket = time.Minute

// DefaultLag is how far behind the ingest watermark the minute layer publishes.
//
// It exists to let the late-arrival window close before a number is shown.
// Measured on the extract: 7.0% of rows arrive out of order, and the generator's
// own --late-max default is 2m, so five minutes clears both with room. It does not
// clear the p99 within-session lateness of 2.3h — nothing short of hours does,
// which is precisely why there is a best-effort live layer as well as this one.
const DefaultLag = 5 * time.Minute

// Runner executes the pipeline against one ClickHouse service.
type Runner struct {
	Client             *chx.Client
	PolicyVersion      string
	HeartbeatTimeoutMS uint64
	LookbackDays       uint16
}

// NewRunner returns a Runner with the measured defaults applied.
func NewRunner(client *chx.Client) *Runner {
	return &Runner{
		Client:             client,
		PolicyVersion:      DefaultPolicyVersion,
		HeartbeatTimeoutMS: DefaultHeartbeatTimeoutMS,
		LookbackDays:       LiveLookbackDays,
	}
}

// Stats reports what one layer's build did, and is also what gets stamped into
// serving_watermark for the freshness tiles.
type Stats struct {
	Layer        string
	WatermarkTS  time.Time
	IntervalsIn  uint64
	RowsOut      uint64
	Build        time.Duration
	SessionsIn   uint64 // intervals layer only
	PartitionsIn uint64 // minute layer only
}

func (s Stats) String() string {
	b := fmt.Sprintf("%-9s watermark=%s rows_out=%d in=%.1fs",
		s.Layer, s.WatermarkTS.UTC().Format("2006-01-02 15:04:05.000"), s.RowsOut, s.Build.Seconds())
	if s.SessionsIn > 0 {
		b += fmt.Sprintf(" sessions=%d", s.SessionsIn)
	}
	if s.IntervalsIn > 0 {
		b += fmt.Sprintf(" intervals=%d", s.IntervalsIn)
	}
	if s.PartitionsIn > 0 {
		b += fmt.Sprintf(" days=%d", s.PartitionsIn)
	}
	return b
}

// statement returns one embedded .sql file with {{db}} resolved.
//
// Each file holds exactly one statement, so unlike chx.SchemaStatements there is
// nothing to split — and nothing that could mis-split a query this size.
func (r *Runner) statement(name string) (string, error) {
	raw, err := fs.ReadFile(sqlFS, "sql/"+name)
	if err != nil {
		return "", fmt.Errorf("read embedded sql/%s: %w", name, err)
	}
	sql := r.Client.Render(string(raw), false)
	if strings.Contains(sql, "{{") {
		return "", fmt.Errorf("sql/%s still holds an unresolved {{...}} placeholder", name)
	}
	return sql, nil
}

// tsParam formats a timestamp for a query parameter.
//
// Millisecond precision, matching every DateTime64(3) in this schema, and always
// UTC — the only timezone this pipeline stores. It exists because the driver
// renders a bound time.Time as toDateTime('...'), which loses the milliseconds and
// which a DateTime64 parameter rejects outright, so every timestamp crosses as a
// String and is cast on the server.
func tsParam(t time.Time) string {
	return t.UTC().Format("2006-01-02 15:04:05.000")
}

func (r *Runner) scalarUint64(ctx context.Context, query string, args ...any) (uint64, error) {
	var v uint64
	if err := r.Client.Conn.QueryRow(ctx, query, args...).Scan(&v); err != nil {
		return 0, err
	}
	return v, nil
}

// Watermark returns the ingest watermark: the newest event time visible in the
// deduplicated layer.
//
// Read from events_dedup rather than taken as now(), because the two differ and
// the difference is exactly the ingest lag. Using now() would claim the pipeline
// had processed events it has not received.
func (r *Runner) Watermark(ctx context.Context) (time.Time, error) {
	var ts time.Time
	q := fmt.Sprintf("SELECT max(event_ts) FROM %s.events_dedup", r.Client.Database)
	if err := r.Client.Conn.QueryRow(ctx, q).Scan(&ts); err != nil {
		return time.Time{}, err
	}
	return ts.UTC(), nil
}

// DirtySessions returns sessions whose events landed after since, which is the
// incremental workset for the intervals layer.
//
// dirty_sessions is written by an insert-time materialized view on events_raw, so
// this is a small index lookup rather than a scan of the event table. The cap
// bounds a single tick: if a bulk load has dirtied more sessions than that, the
// caller should do a full rebuild instead of trying to catch up in slices.
func (r *Runner) DirtySessions(ctx context.Context, since time.Time, cap int) ([]uint64, error) {
	q := fmt.Sprintf(`
		SELECT DISTINCT session_key
		FROM %s.dirty_sessions
		WHERE last_ingested_at > toDateTime64({since:String}, 3, 'UTC')
		LIMIT {cap:UInt64}`, r.Client.Database)

	// Timestamps cross as formatted strings and are cast server-side. The driver
	// renders a bound time.Time as toDateTime('...'), which a DateTime64
	// parameter refuses to parse — the same reason 010 declares evaluation_as_of
	// as a String.
	rows, err := r.Client.Conn.Query(ctx, q, chx.Named("since", tsParam(since)), chx.Named("cap", uint64(cap)))
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var keys []uint64
	for rows.Next() {
		var k uint64
		if err := rows.Scan(&k); err != nil {
			return nil, err
		}
		keys = append(keys, k)
	}
	return keys, rows.Err()
}

// Intervals recomputes session_intervals.
//
// An empty sessionKeys means every session. Recomputation REPLACES each session's
// row rather than adjusting it, so running this twice on the same input is a
// no-op beyond a bumped version — which is what makes a retry safe and removes
// the need for any correction ledger.
func (r *Runner) Intervals(ctx context.Context, sessionKeys []uint64, evaluationAsOf time.Time) (Stats, error) {
	started := time.Now()
	sql, err := r.statement("010_recompute_sessions.sql")
	if err != nil {
		return Stats{}, err
	}
	if sessionKeys == nil {
		// The SQL tests emptiness with empty(), which needs a real empty array
		// rather than a nil the driver might send as NULL.
		sessionKeys = []uint64{}
	}

	err = r.Client.Conn.Exec(ctx, sql,
		chx.Named("session_keys", sessionKeys),
		chx.Named("heartbeat_timeout_ms", r.HeartbeatTimeoutMS),
		chx.Named("evaluation_as_of", tsParam(evaluationAsOf)),
		chx.Named("policy_version", r.PolicyVersion),
		chx.Named("version", uint64(time.Now().UnixMilli())),
	)
	if err != nil {
		return Stats{}, fmt.Errorf("recompute session_intervals: %w", err)
	}

	st := Stats{Layer: "intervals", WatermarkTS: evaluationAsOf, Build: time.Since(started), SessionsIn: uint64(len(sessionKeys))}
	if st.RowsOut, err = r.scalarUint64(ctx,
		fmt.Sprintf("SELECT sum(length(intervals)) FROM %s.session_intervals FINAL", r.Client.Database)); err != nil {
		return st, err
	}
	st.IntervalsIn = st.RowsOut
	return st, r.stampWatermark(ctx, st)
}

// Live rebuilds serving_concurrency_live over [windowStart, windowEnd).
//
// Best-effort by construction: it publishes without waiting for the late-arrival
// window to close, so a late event can change an already-published bucket. That
// is the trade a "right now" number makes, and the dashboard says so.
//
// BOTH window edges are aligned to a bucket boundary, and both matter. The rollup
// clips intervals to the window, so any edge landing mid-bucket truncates that
// bucket's contribution:
//
//   - a mid-bucket END clips every still-open session at that instant, making the
//     newest bucket's ending_concurrency 0 and its active_ms a fraction of the
//     truth. Measured: a live layer sitting at ~600 concurrent reported
//     "concurrent now" as 0 on every single pass, because the newest bucket was
//     always the broken one.
//   - a mid-bucket START is the same defect at the other end, and it is worse
//     because it PERSISTS. The window slides 10s per pass while bucket boundaries
//     stay fixed, so the last pass that ever touches a given bucket is the one
//     where it sits at the window's leading edge — partially clipped. Nothing
//     rewrites it afterwards. Measured against ground truth recomputed from
//     session_intervals: seven consecutive minutes held roughly a third of their
//     real active_ms, e.g. 3,245,803 ms recorded against 9,456,921 ms actual.
//
// Truncate is relative to the epoch, so it lands on the same 10-second boundaries
// as the intDiv(ms, 10000) bucketing in the SQL. Both edges aligned costs up to one
// bucket of freshness and makes every published bucket whole.
//
// The cross-layer invariant in 090_validate_serving.sql is what surfaced the second
// one: the minute layer agreed with ground truth and the live layer did not.
func (r *Runner) Live(ctx context.Context, windowStart, windowEnd time.Time) (Stats, error) {
	started := time.Now()
	sql, err := r.statement("020_rollup_live.sql")
	if err != nil {
		return Stats{}, err
	}
	windowStart = windowStart.Truncate(LiveBucket)
	windowEnd = windowEnd.Truncate(LiveBucket)

	before, err := r.scalarUint64(ctx, fmt.Sprintf("SELECT count() FROM %s.serving_concurrency_live", r.Client.Database))
	if err != nil {
		return Stats{}, err
	}

	err = r.Client.Conn.Exec(ctx, sql,
		chx.Named("window_start", tsParam(windowStart)),
		chx.Named("window_end", tsParam(windowEnd)),
		chx.Named("lookback_days", r.LookbackDays),
		chx.Named("version", uint64(time.Now().UnixMilli())),
	)
	if err != nil {
		return Stats{}, fmt.Errorf("rollup live: %w", err)
	}

	after, err := r.scalarUint64(ctx, fmt.Sprintf("SELECT count() FROM %s.serving_concurrency_live", r.Client.Database))
	if err != nil {
		return Stats{}, err
	}

	st := Stats{Layer: "live", WatermarkTS: windowEnd, RowsOut: after - before, Build: time.Since(started)}
	return st, r.stampWatermark(ctx, st)
}

// Minute rebuilds one whole UTC day of serving_concurrency_minute.
//
// Staged and swapped rather than inserted, because a rebuild has to be able to
// REMOVE rows the recompute no longer produces — a session that loses all its
// active time in some minute must leave no row behind, and replacement semantics
// have nothing to replace it with. REPLACE PARTITION does that atomically, so a
// reader never sees the day half-built.
//
// An empty staging partition means the day genuinely has no concurrency, and the
// destination partition is dropped instead of swapped: REPLACE PARTITION from a
// source that has no such partition is not a reliable way to express deletion.
func (r *Runner) Minute(ctx context.Context, day, publishUntil time.Time) (Stats, error) {
	started := time.Now()
	sql, err := r.statement("030_rollup_minute.sql")
	if err != nil {
		return Stats{}, err
	}
	publishUntil = publishUntil.Truncate(MinuteBucket)

	date := day.UTC().Format("2006-01-02")
	partID := day.UTC().Format("20060102") // matches PARTITION BY toYYYYMMDD(minute_start)
	db := r.Client.Database

	// Clear only this day from staging. Other days may be in flight from a
	// concurrent rebuild of a different partition, and TRUNCATE would take them
	// with it.
	if err := r.Client.Conn.Exec(ctx,
		fmt.Sprintf("ALTER TABLE %s.serving_concurrency_minute_staging DROP PARTITION ID '%s'", db, partID)); err != nil {
		return Stats{}, fmt.Errorf("clear staging partition %s: %w", partID, err)
	}

	if err := r.Client.Conn.Exec(ctx, sql,
		chx.Named("service_date", date),
		chx.Named("publish_until", tsParam(publishUntil)),
		chx.Named("lookback_days", r.LookbackDays),
	); err != nil {
		return Stats{}, fmt.Errorf("rollup minute %s: %w", date, err)
	}

	staged, err := r.scalarUint64(ctx,
		fmt.Sprintf("SELECT count() FROM %s.serving_concurrency_minute_staging WHERE toYYYYMMDD(minute_start) = %s", db, partID))
	if err != nil {
		return Stats{}, err
	}

	if staged == 0 {
		if err := r.Client.Conn.Exec(ctx,
			fmt.Sprintf("ALTER TABLE %s.serving_concurrency_minute DROP PARTITION ID '%s'", db, partID)); err != nil {
			return Stats{}, fmt.Errorf("drop empty day %s: %w", date, err)
		}
	} else {
		if err := r.Client.Conn.Exec(ctx, fmt.Sprintf(
			"ALTER TABLE %s.serving_concurrency_minute REPLACE PARTITION ID '%s' FROM %s.serving_concurrency_minute_staging",
			db, partID, db)); err != nil {
			return Stats{}, fmt.Errorf("swap day %s: %w", date, err)
		}
		// Staging is scratch space, not a second copy of the serving data.
		if err := r.Client.Conn.Exec(ctx,
			fmt.Sprintf("ALTER TABLE %s.serving_concurrency_minute_staging DROP PARTITION ID '%s'", db, partID)); err != nil {
			return Stats{}, fmt.Errorf("clear staging after swap %s: %w", date, err)
		}
	}

	// The watermark is what this layer will actually SHOW, so it is the publish
	// cutoff clipped to the day — not end-of-day and not the ingest watermark.
	// Reporting either of those would claim freshness the layer deliberately does
	// not have, and the freshness tile would then read near-zero while the newest
	// visible minute was five minutes old.
	watermark := day.UTC().Add(24 * time.Hour)
	if publishUntil.Before(watermark) {
		watermark = publishUntil
	}

	st := Stats{Layer: "minute", WatermarkTS: watermark, RowsOut: staged, Build: time.Since(started), PartitionsIn: 1}
	return st, r.stampWatermark(ctx, st)
}

// ServiceDays lists the UTC days that session_intervals has any active time in.
//
// Derived from the intervals rather than from event dates, because an interval
// can extend past midnight into a day that has no events of its own — and that
// day still needs minute rows.
func (r *Runner) ServiceDays(ctx context.Context) ([]time.Time, error) {
	return r.ServiceDaysFor(ctx, nil)
}

// ServiceDaysFor lists the UTC days that the given sessions have active time in.
// A nil or empty sessionKeys means every session.
//
// This is what makes an incremental minute rebuild possible. Without it the loop
// rebuilt every service day on every pass, which on this extract meant rewriting
// the 172,187-row hot day once a minute to publish a handful of newly settled
// minutes — measured at 64 rebuilds and 1,005,500 rows rewritten per ten minutes.
// Scoping to the days the recomputed sessions actually touch makes the work
// proportional to what changed.
func (r *Runner) ServiceDaysFor(ctx context.Context, sessionKeys []uint64) ([]time.Time, error) {
	// Two derivations, because the scoped case has to over-approximate.
	//
	// Unscoped reads the days the intervals actually cover. Exact, and what a full
	// rebuild wants.
	//
	// Scoped derives from session_start_date instead, expanded by LookbackDays.
	// Reading current intervals would be unsound: if late data SHRINKS a session so
	// its intervals no longer cross midnight, the day it used to occupy would not
	// appear, would not be rebuilt, and would keep a stale row indefinitely. A
	// session that loses all its active time reports no days at all.
	// session_start_date is stable per session — it is the partition key of
	// session_intervals precisely so a session never migrates — so
	// [start_date, start_date + LookbackDays] always contains every day the session
	// could touch, before or after the recompute.
	//
	// Over-approximating is the safe direction: 030 rebuilds a whole day from ALL
	// sessions, so an extra day costs time and nothing else, whereas a missed day is
	// silent staleness.
	var q string
	var args []any
	if len(sessionKeys) == 0 {
		q = fmt.Sprintf(`
			SELECT DISTINCT toDate(d) AS service_date
			FROM (
				SELECT arrayJoin(arrayMap(
					i -> toDateTime64(i, 3, 'UTC'),
					range(
						toUInt64(toUnixTimestamp(toStartOfDay(ivl.1))),
						toUInt64(toUnixTimestamp(toStartOfDay(ivl.2))) + 86400,
						86400))) AS d
				FROM (SELECT arrayJoin(intervals) AS ivl FROM %s.session_intervals FINAL)
			)
			ORDER BY service_date`, r.Client.Database)
	} else {
		q = fmt.Sprintf(`
			SELECT DISTINCT
				session_start_date + toIntervalDay(arrayJoin(range(0, {span:UInt16}))) AS service_date
			FROM %s.session_intervals FINAL
			WHERE session_key IN {session_keys:Array(UInt64)}
			ORDER BY service_date`, r.Client.Database)
		args = []any{
			chx.Named("session_keys", sessionKeys),
			chx.Named("span", uint16(r.LookbackDays)+1),
		}
	}

	rows, err := r.Client.Conn.Query(ctx, q, args...)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var days []time.Time
	for rows.Next() {
		var d time.Time
		if err := rows.Scan(&d); err != nil {
			return nil, err
		}
		days = append(days, d.UTC())
	}
	if err := rows.Err(); err != nil {
		return nil, err
	}
	sort.Slice(days, func(i, j int) bool { return days[i].Before(days[j]) })
	return days, nil
}

// stampWatermark records how current a layer is, in both the current-state table
// the freshness tiles read and the append-only history the build-latency series
// plots. Two tables because a ReplacingMergeTree keyed on layer keeps exactly one
// row per layer by design and so cannot answer "how long did builds take".
func (r *Runner) stampWatermark(ctx context.Context, st Stats) error {
	db := r.Client.Database
	args := []any{
		chx.Named("layer", st.Layer),
		chx.Named("watermark_ts", tsParam(st.WatermarkTS)),
		chx.Named("policy_version", r.PolicyVersion),
		chx.Named("intervals_in", st.IntervalsIn),
		chx.Named("rows_out", st.RowsOut),
		chx.Named("build_ms", uint64(st.Build.Milliseconds())),
	}

	if err := r.Client.Conn.Exec(ctx, fmt.Sprintf(`
		INSERT INTO %s.serving_watermark
			(layer, watermark_ts, built_at, policy_version, intervals_in, rows_out, build_ms, version)
		SELECT {layer:String}, {watermark_ts:DateTime64(3,'UTC')}, now64(3), {policy_version:String},
		       {intervals_in:UInt64}, {rows_out:UInt64}, {build_ms:UInt64}, toUnixTimestamp64Milli(now64(3))`, db),
		args...); err != nil {
		return fmt.Errorf("stamp watermark for %s: %w", st.Layer, err)
	}

	if err := r.Client.Conn.Exec(ctx, fmt.Sprintf(`
		INSERT INTO %s.serving_watermark_history
			(layer, watermark_ts, built_at, policy_version, intervals_in, rows_out, build_ms)
		SELECT {layer:String}, {watermark_ts:DateTime64(3,'UTC')}, now64(3), {policy_version:String},
		       {intervals_in:UInt64}, {rows_out:UInt64}, {build_ms:UInt64}`, db),
		args...); err != nil {
		return fmt.Errorf("append watermark history for %s: %w", st.Layer, err)
	}
	return nil
}
