package pipelinehealth

import (
	"context"
	"fmt"
	"time"

	"github.com/ClickHouse/clickhouse-go/v2/lib/driver"
)

// BuildStage is one stage of tools/build-model.sh, reconstructed from
// system.query_log rather than re-run: build-model.sh truncates and
// re-inserts session_intervals and cc_minute_delta in order, and each INSERT
// is already a row in ClickHouse's own query log, complete with the duration
// and row counts a client-side timer could only approximate. Re-deriving
// stage duration from a client wrapper around the real script would be
// strictly worse data than what the server already recorded — the same
// reasoning that keeps benchmark-query latency out of this package entirely
// (system.query_log is authoritative for that; see docs/OBSERVABILITY.md).
type BuildStage struct {
	Stage               string
	Found               bool
	LastRunAt           time.Time
	DurationMS          uint64
	RowsRead            uint64
	RowsWritten         uint64
	SecondsSinceLastRun float64
}

// QueryBuildStages returns the most recent run of each build-model.sh stage
// against database `db` (so the same code works against sonyliv on Cloud or
// default locally). It distinguishes stages by which tables the INSERT
// touched: session_intervals is written FROM ev_raw; cc_minute_delta is
// written FROM session_intervals and never touches ev_raw directly.
func QueryBuildStages(ctx context.Context, conn driver.Conn, db string) ([]BuildStage, error) {
	stages := []struct {
		name  string
		where string
	}{
		{
			name: "session_intervals",
			where: fmt.Sprintf(
				`has(tables, '%s.session_intervals') AND has(tables, '%s.ev_raw')`, db, db,
			),
		},
		{
			name: "cc_minute_delta",
			where: fmt.Sprintf(
				`has(tables, '%s.cc_minute_delta') AND has(tables, '%s.session_intervals') AND NOT has(tables, '%s.ev_raw')`,
				db, db, db,
			),
		},
	}

	now := time.Now()
	out := make([]BuildStage, 0, len(stages))
	for _, s := range stages {
		bs, err := queryLatestInsert(ctx, conn, s.name, s.where, now)
		if err != nil {
			return nil, fmt.Errorf("build stage %q: %w", s.name, err)
		}
		out = append(out, bs)
	}
	return out, nil
}

func queryLatestInsert(ctx context.Context, conn driver.Conn, stage, where string, now time.Time) (BuildStage, error) {
	q := fmt.Sprintf(`
		SELECT event_time, query_duration_ms, read_rows, written_rows
		FROM system.query_log
		WHERE type = 'QueryFinish' AND query_kind = 'Insert' AND (%s)
		ORDER BY event_time DESC
		LIMIT 1`, where)

	row := conn.QueryRow(ctx, q)

	var (
		eventTime             time.Time
		durationMS            uint64
		readRows, writtenRows uint64
	)
	if err := row.Scan(&eventTime, &durationMS, &readRows, &writtenRows); err != nil {
		if isNoRowsErr(err) {
			return BuildStage{Stage: stage, Found: false}, nil
		}
		return BuildStage{}, fmt.Errorf("query system.query_log: %w", err)
	}

	return BuildStage{
		Stage:               stage,
		Found:               true,
		LastRunAt:           eventTime,
		DurationMS:          durationMS,
		RowsRead:            readRows,
		RowsWritten:         writtenRows,
		SecondsSinceLastRun: now.Sub(eventTime).Seconds(),
	}, nil
}
