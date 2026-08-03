package profiler

import (
	"strings"
	"testing"
)

func TestProfileFlattensAndTypesEvents(t *testing.T) {
	sample := `{"event":"checkout_shown","timestamp":"2026-06-08T06:00:00.000","application_id":"a1","payment":{"amount":42.5}}
{"event":"checkout_completed","timestamp":"2026-06-08T06:01:00.000","application_id":"a1","payment":{"amount":42.5}}`
	profile, err := Profile(sample)
	if err != nil {
		t.Fatal(err)
	}
	if profile.Rows != 2 || len(profile.EventOrder) != 2 {
		t.Fatalf("unexpected profile: %#v", profile)
	}
	foundNested := false
	for _, field := range profile.Fields {
		if field.ColumnName == "payment_amount" && field.ClickHouseType == "Float64" {
			foundNested = true
		}
	}
	if !foundNested {
		t.Fatal("nested numeric field was not flattened and typed")
	}
}

func TestProfileSkipsMalformedLinesGracefully(t *testing.T) {
	lines := []string{}
	for i := 0; i < 20; i++ {
		lines = append(lines, `{"event":"checkout_shown","id":"a"}`)
	}
	lines = append(lines, `{"event":"checkout_shown","id":`)
	profile, err := Profile(strings.Join(lines, "\n"))
	if err != nil {
		t.Fatalf("one malformed line among twenty should not fail the profile: %v", err)
	}
	if profile.Rows != 20 || profile.SkippedRows != 1 {
		t.Fatalf("unexpected counts: rows=%d skipped=%d", profile.Rows, profile.SkippedRows)
	}
	found := false
	for _, warning := range profile.Warnings {
		if strings.Contains(warning, "line 21") {
			found = true
		}
	}
	if !found {
		t.Fatalf("skipped line was not reported in warnings: %#v", profile.Warnings)
	}
}

func TestProfileRejectsMostlyMalformedSample(t *testing.T) {
	sample := `{"event":"checkout_shown"}
not json at all
{"event":"checkout_shown"`
	if _, err := Profile(sample); err == nil {
		t.Fatal("a sample with 2 of 3 lines malformed must be rejected")
	}
	if _, err := Profile("garbage\nmore garbage"); err == nil {
		t.Fatal("a sample with zero valid rows must be rejected")
	}
}
