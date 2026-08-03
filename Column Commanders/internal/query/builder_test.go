package query

import (
	"strings"
	"testing"
)

func TestRuntimeSQLUsesConfiguredConnectionDatabase(t *testing.T) {
	queries := []string{
		GetDataAnchorSQL,
		GetDataAnchorFallbackSQL,
		DailyZScoreBaselineSQL,
		HourlyZScoreBaselineSQL,
		RollingCUSUMFillRateSQL,
		RollingCUSUMECPMSQL,
		RollingCUSUMDailyFillRateSQL,
		RollingCUSUMDailyECPMSQL,
		FactorDecompositionSQL,
		contributionSQLTemplate,
		segmentZScoreSQLTemplate,
		UpsertIncidentSQL,
	}
	for i, sql := range queries {
		if strings.Contains(sql, "inmobi.") || strings.Contains(sql, "inmobi-analytics.") {
			t.Errorf("query %d hard-codes a database: %s", i+1, sql)
		}
	}
}

func TestAnchorQueriesPreserveTimeOfDay(t *testing.T) {
	if strings.Contains(GetDataAnchorSQL, "toDate(") || strings.Contains(GetDataAnchorFallbackSQL, "toDate(") {
		t.Fatal("data-anchor queries must preserve time for hourly detection")
	}
}
