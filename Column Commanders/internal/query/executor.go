package query

import (
	"context"
	"errors"
	"fmt"
	"log/slog"
	"strings"
	"time"

	"clickhouse-go-service/internal/db"
)

// defaultQuerySettings bounds every SELECT this service issues — a judge-driven
// follow-up, a pathological window, or a future query template that forgets its
// own limits should never be able to run unbounded against ClickHouse Cloud.
// See docs/CLICKHOUSE_REVIEW.md's agent-query-safety rule (CRITICAL).
const defaultQuerySettings = "SETTINGS max_execution_time = 30, max_rows_to_read = 1000000000, max_result_rows = 10000, timeout_before_checking_execution_speed = 0"

// withSafetySettings appends the default safety settings unless the query
// already declares its own SETTINGS clause (never silently override one).
func withSafetySettings(sql string) string {
	if strings.Contains(strings.ToUpper(sql), "SETTINGS") {
		return sql
	}
	return sql + "\n" + defaultQuerySettings
}

// Executor wraps db.Client and adds structured logging to every query.
// All Rows/Row/Exec calls accept named parameters as alternating key-value pairs:
//
//	e.Rows(ctx, "my_query", sql, "param1", val1, "param2", val2)
//
// Internally these are converted to clickhouse.Named() for the native protocol driver.
type Executor struct {
	db     *db.Client
	logger *slog.Logger
}

// NewExecutor creates an Executor.
func NewExecutor(dbClient *db.Client, logger *slog.Logger) *Executor {
	return &Executor{db: dbClient, logger: logger}
}

// Rows executes a SELECT and returns results as []map[string]any.
// params: alternating key-value pairs for {param:Type} SQL bindings.
func (e *Executor) Rows(ctx context.Context, queryName, sql string, params ...any) ([]map[string]any, error) {
	t0 := time.Now()
	named := db.Named(params...)
	rows, err := e.db.QueryRows(ctx, withSafetySettings(sql), named...)
	elapsed := time.Since(t0)

	if err != nil {
		e.logger.Error("query failed",
			slog.String("query", queryName),
			slog.Int64("elapsed_ms", elapsed.Milliseconds()),
			slog.Any("error", err),
		)
		return nil, fmt.Errorf("%s: %w", queryName, err)
	}

	e.logger.Info("query ok",
		slog.String("query", queryName),
		slog.Int64("elapsed_ms", elapsed.Milliseconds()),
		slog.Int("rows", len(rows)),
	)
	return rows, nil
}

// Row executes a SELECT expected to return exactly one row.
func (e *Executor) Row(ctx context.Context, queryName, sql string, params ...any) (map[string]any, error) {
	t0 := time.Now()
	named := db.Named(params...)
	row, err := e.db.QueryRow(ctx, withSafetySettings(sql), named...)
	elapsed := time.Since(t0)

	if err != nil {
		if errors.Is(err, db.ErrNoRows) {
			e.logger.Warn("query returned no rows",
				slog.String("query", queryName),
				slog.Int64("elapsed_ms", elapsed.Milliseconds()),
			)
		} else {
			e.logger.Error("query failed",
				slog.String("query", queryName),
				slog.Int64("elapsed_ms", elapsed.Milliseconds()),
				slog.Any("error", err),
			)
		}
		return nil, fmt.Errorf("%s: %w", queryName, err)
	}

	e.logger.Info("query ok",
		slog.String("query", queryName),
		slog.Int64("elapsed_ms", elapsed.Milliseconds()),
	)
	return row, nil
}

// Exec executes a statement that returns no rows (DDL, INSERT).
func (e *Executor) Exec(ctx context.Context, queryName, sql string, params ...any) error {
	t0 := time.Now()
	var err error
	if len(params) == 0 {
		err = e.db.Exec(ctx, sql)
	} else {
		named := db.Named(params...)
		err = e.db.Exec(ctx, sql, named...)
	}
	elapsed := time.Since(t0)

	if err != nil {
		e.logger.Error("exec failed",
			slog.String("query", queryName),
			slog.Int64("elapsed_ms", elapsed.Milliseconds()),
			slog.Any("error", err),
		)
		return fmt.Errorf("%s: %w", queryName, err)
	}

	e.logger.Debug("exec ok",
		slog.String("query", queryName),
		slog.Int64("elapsed_ms", elapsed.Milliseconds()),
	)
	return nil
}

// InsertRows writes a bounded batch into a trusted application-owned table.
// Table and column names must come from code, never from an HTTP or LLM input.
func (e *Executor) InsertRows(ctx context.Context, queryName, table string, cols []string, rows []map[string]any) error {
	t0 := time.Now()
	if err := e.db.InsertRows(ctx, table, cols, rows); err != nil {
		e.logger.Error("insert failed",
			slog.String("query", queryName),
			slog.String("table", table),
			slog.Int("rows", len(rows)),
			slog.Any("error", err),
		)
		return fmt.Errorf("%s: %w", queryName, err)
	}
	e.logger.Info("insert ok",
		slog.String("query", queryName),
		slog.String("table", table),
		slog.Int("rows", len(rows)),
		slog.Int64("elapsed_ms", time.Since(t0).Milliseconds()),
	)
	return nil
}
