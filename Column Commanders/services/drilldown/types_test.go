package drilldown

import (
	"strings"
	"testing"
)

func TestDimensionQueriesUseConfiguredConnectionDatabase(t *testing.T) {
	for _, dimension := range AllDimensions {
		if strings.Contains(dimension.FromClause, "inmobi.") || strings.Contains(dimension.FromClause, "inmobi-analytics.") {
			t.Errorf("dimension %q hard-codes a database: %s", dimension.Key, dimension.FromClause)
		}
	}
}
