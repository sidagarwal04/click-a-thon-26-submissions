package agent

import (
	"testing"

	"github.com/view26/featurelens/internal/domain"
)

func TestInstrumentationUsesExplicitSchemaVersion(t *testing.T) {
	profile := domain.EventProfile{Fields: []domain.FieldProfile{
		{ColumnName: "event_name", Path: "event", ClickHouseType: "String"},
		{ColumnName: "timestamp", Path: "timestamp", ClickHouseType: "DateTime64(3, 'UTC')"},
		{ColumnName: "application_id", Path: "application_id", ClickHouseType: "Nullable(String)", Nullable: true},
	}}
	proposal := (InstrumentationAgent{Database: "atlys"}).Design(domain.FeatureInput{Name: "Group / Family", Slug: "group_family", SchemaVersion: 2}, profile)
	if proposal.Version != 2 || proposal.Table != "group_family_events_v2" {
		t.Fatalf("expected versioned v2 table, got v%d %s", proposal.Version, proposal.Table)
	}
}

func TestInstrumentationTargetUsesRequestedSchemaVersion(t *testing.T) {
	database, table, version := (InstrumentationAgent{Database: "featurelens"}).Target(domain.FeatureInput{Name: "Group / Family", SchemaVersion: 2})
	if database != "featurelens" || table != "group_family_events_v2" || version != 2 {
		t.Fatalf("unexpected target: %s.%s v%d", database, table, version)
	}
}
