package investigation

import (
	"strings"
	"testing"
	"time"

	"clickhouse-go-service/internal/config"
	"clickhouse-go-service/services/anomalydetector"
)

func testValidator() *Validator {
	return NewValidator(config.DetectionConfig{
		AgentQueryTimeout: 3 * time.Second, AgentMaxRowsRead: 1000,
		AgentMaxBytesRead: 2000, AgentMaxResultRows: 100,
	})
}

const validAgentSQL = `SELECT e.ad_format AS segment, sum(e.revenue) AS revenue
FROM ad_events AS e
WHERE e.event_time >= toDateTime64({window_start:String}, 3, 'UTC')
  AND e.event_time < toDateTime64({window_end:String}, 3, 'UTC')
GROUP BY segment ORDER BY revenue DESC LIMIT 10`

func TestValidatorHardensApprovedQuery(t *testing.T) {
	validated, err := testValidator().Validate(QueryRequest{Purpose: "rank impact", SQL: validAgentSQL, ExpectedColumns: []string{"segment", "revenue"}}, anomalydetector.ModeRealTime)
	if err != nil {
		t.Fatal(err)
	}
	for _, required := range []string{"max_execution_time = 3", "max_rows_to_read = 1000", "max_bytes_to_read = 2000", "prefer_column_name_to_alias = 1"} {
		if !strings.Contains(validated.SQL, required) {
			t.Errorf("hardened SQL missing %q", required)
		}
	}
}

func TestValidatorAllowsCTEsBackedByApprovedTables(t *testing.T) {
	sql := `WITH filtered_events AS (
	SELECT ad_format, revenue, event_time
	FROM ad_events
	WHERE event_time >= toDateTime64({window_start:String}, 3, 'UTC')
	  AND event_time < toDateTime64({window_end:String}, 3, 'UTC')
)
SELECT ad_format AS segment, sum(revenue) AS revenue
FROM filtered_events
GROUP BY segment ORDER BY revenue DESC LIMIT 10`
	if _, err := testValidator().Validate(QueryRequest{
		Purpose: "rank impact", SQL: sql, ExpectedColumns: []string{"segment", "revenue"},
	}, anomalydetector.ModeHistorical); err != nil {
		t.Fatalf("expected approved-table CTE to pass validation: %v", err)
	}
}

func TestValidatorRejectsCTEBackedOnlyByUnapprovedTable(t *testing.T) {
	sql := `WITH filtered AS (
	SELECT event_time FROM secret_events
	WHERE event_time >= toDateTime64({window_start:String}, 3, 'UTC')
	  AND event_time < toDateTime64({window_end:String}, 3, 'UTC')
)
SELECT event_time FROM filtered LIMIT 10`
	if _, err := testValidator().Validate(QueryRequest{
		Purpose: "unsafe", SQL: sql, ExpectedColumns: []string{"event_time"},
	}, anomalydetector.ModeHistorical); err == nil {
		t.Fatal("expected unapproved physical table inside CTE to be rejected")
	}
}

func TestValidatorRejectsUnsafeAgentSQL(t *testing.T) {
	tests := []string{
		"DROP TABLE ad_events",
		"SELECT x FROM system.tables WHERE event_time >= {window_start:String} AND event_time < {window_end:String} LIMIT 1",
		"SELECT avg(ctr) FROM metrics_global_1m WHERE window_start >= {window_start:String} AND window_start < {window_end:String} LIMIT 1",
		"SELECT * FROM ad_events WHERE event_time >= {window_start:String} AND event_time < {window_end:String} LIMIT 1",
		"SELECT revenue FROM ad_events LIMIT 10",
	}
	for _, sql := range tests {
		if _, err := testValidator().Validate(QueryRequest{Purpose: "unsafe", SQL: sql, ExpectedColumns: []string{"x"}}, anomalydetector.ModeRealTime); err == nil {
			t.Errorf("expected rejection for %q", sql)
		}
	}
}
