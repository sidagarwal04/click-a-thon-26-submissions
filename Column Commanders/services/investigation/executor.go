package investigation

import (
	"context"
	"fmt"
	"time"

	"clickhouse-go-service/internal/query"
)

type QueryResult struct {
	Purpose string           `json:"purpose"`
	Rows    []map[string]any `json:"rows"`
}

type QueryExecutor struct {
	qe *query.Executor
}

func NewQueryExecutor(qe *query.Executor) *QueryExecutor { return &QueryExecutor{qe: qe} }

func (e *QueryExecutor) Execute(ctx context.Context, queryIndex int, validated ValidatedQuery, start, end time.Time) (QueryResult, error) {
	rows, err := e.qe.Rows(ctx, fmt.Sprintf("investigation_agent_%d", queryIndex), validated.SQL,
		"window_start", formatWindowParameter(start),
		"window_end", formatWindowParameter(end),
	)
	if err != nil {
		return QueryResult{}, err
	}
	if len(rows) > 0 {
		for _, expected := range validated.ExpectedColumns {
			if _, ok := rows[0][expected]; !ok {
				return QueryResult{}, fmt.Errorf("query result missing expected column %q", expected)
			}
		}
	}
	return QueryResult{Purpose: validated.Purpose, Rows: rows}, nil
}

// Seconds are accepted by both toDateTime and toDateTime64. Fractional text is
// rejected when an agent chooses toDateTime for a {name:String} parameter.
func formatWindowParameter(value time.Time) string {
	return value.UTC().Format("2006-01-02 15:04:05")
}
